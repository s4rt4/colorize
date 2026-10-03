import json

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent, QGuiApplication

from colorize.formats import colorize_json
from colorize.formats.swatch_files import read_ase, write_ase, write_gpl


@pytest.fixture
def export(window):
    panel = window.panels["export"]
    window.docks["export"].setAsCurrentTab()
    return panel


def select(combo, key):
    combo.setCurrentIndex(combo.findData(key))


# ------------------------------------------------------------------ export


def test_export_preview_follows_options(window, export):
    select(export.format, "css")
    assert "--untitled-1-1: #1f3a5f;" in export.preview.toPlainText()
    export.prefix.setText("Brand")
    assert "--brand-1: #1f3a5f;" in export.preview.toPlainText()
    select(export.syntax, "rgb")
    assert "--brand-1: rgb(31 58 95);" in export.preview.toPlainText()
    select(export.format, "tokens")
    assert not export.syntax.isEnabled()
    assert json.loads(export.preview.toPlainText())["brand"]["$type"] == "color"
    select(export.format, "ase")
    assert export.preview.toPlainText().startswith("Binary file")
    assert not export.copy_button.isEnabled()


def test_export_follows_palette_edits_and_rename(window, export):
    select(export.format, "list")
    window.state.set_foreground("#ABCDEF")
    window.actions["add_fg"].trigger()
    assert export.preview.toPlainText().splitlines()[-1] == "#abcdef"
    window.current_document().rename("Ocean")
    select(export.format, "css")
    assert "--ocean-1:" in export.preview.toPlainText()


def test_copy_puts_text_on_clipboard(window, export):
    select(export.format, "tailwind4")
    export.copy()
    assert QGuiApplication.clipboard().text().startswith("/* Untitled-1")


@pytest.mark.parametrize("fmt, suffix", [("ase", ".ase"), ("gpl", ".gpl"), ("tailwind3", ".js"), ("tokens", ".tokens.json")])
def test_export_writes_files(window, export, tmp_path, monkeypatch, fmt, suffix):
    select(export.format, fmt)
    monkeypatch.setattr(
        "colorize.ui.export_panel.QFileDialog.getSaveFileName", lambda *a, **k: (str(tmp_path / "out"), "")
    )
    path = window.export_palette()
    assert path == str(tmp_path / f"out{suffix}")
    colors = list(window.current_document().palette.colors)
    if fmt == "ase":
        assert read_ase((tmp_path / "out.ase").read_bytes()) == ("Untitled-1", colors)
    else:
        assert (tmp_path / f"out{suffix}").read_text(encoding="utf-8")


def test_export_options_are_remembered(window, export, settings):
    select(export.format, "gpl")
    select(export.syntax, "hsl")
    assert settings.value("export/format") == "gpl"
    assert settings.value("export/syntax") == "hsl"


def test_export_disabled_without_colors(window, export):
    window.close_document()
    assert not export.export_button.isEnabled()
    assert window.export_palette() is None


# ------------------------------------------------------------------ import


@pytest.mark.parametrize("suffix", [".ase", ".gpl"])
def test_opening_swatch_files_imports_them(window, tmp_path, suffix):
    path = tmp_path / f"Ocean{suffix}"
    if suffix == ".ase":
        path.write_bytes(write_ase("Ocean", ["#0077BE", "#FFFFFF"]))
    else:
        path.write_text(write_gpl("Ocean", ["#0077BE", "#FFFFFF"]), encoding="utf-8")
    doc = window.open_file(str(path))
    assert doc.palette.name == "Ocean"
    assert doc.palette.colors == ("#0077BE", "#FFFFFF")
    assert doc.path is None and doc.is_modified  # imported, not our file to save over
    assert str(path.resolve()) in window.library.recent_files()


def test_drop_gpl(window, tmp_path):
    path = tmp_path / "drop.gpl"
    path.write_text(write_gpl("Dropped", ["#123456"]), encoding="utf-8")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    window.dropEvent(QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    assert window.current_document().palette.name == "Dropped"


def test_bad_swatch_file_warns(window, tmp_path, monkeypatch):
    path = tmp_path / "bad.ase"
    path.write_bytes(b"nope")
    warnings = []
    monkeypatch.setattr("colorize.ui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    assert window.open_file(str(path)) is None
    assert "not an Adobe Swatch Exchange file" in warnings[0]


# ----------------------------------------------------------------- library


def test_save_to_library_then_update(window):
    doc = window.current_document()
    pid = window.save_to_library()
    assert window.library.get_palette(pid).colors == doc.palette.colors
    assert not doc.is_modified  # unsaved palette: the library counts as saving it
    window.actions["add_fg"].trigger()
    assert window.save_to_library() == pid  # same entry, updated
    assert len(window.library.get_palette(pid).colors) == len(doc.palette)
    assert len(window.library.palettes()) == 1
    panel = window.panels["library"]
    assert panel.selected().id == pid


def test_library_save_keeps_file_backed_palette_modified(window, tmp_path, monkeypatch):
    monkeypatch.setattr("colorize.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (str(tmp_path / "p.json"), ""))
    window.save_document()
    window.actions["add_fg"].trigger()
    window.save_to_library()
    assert window.current_document().is_modified  # the file on disk is still out of date


def test_open_from_library_and_refocus(window):
    pid = window.library.add_palette("Saved", ["#111111", "#222222"])
    panel = window.panels["library"]
    panel.refresh()
    panel.select_id(pid)
    panel.openRequested.emit(panel.selected())
    doc = window.current_document()
    assert doc.palette.name == "Saved" and doc.library_id == pid
    assert not doc.is_modified
    window.doc_tabs.setCurrentIndex(0)
    assert window.open_from_library(window.library.get_palette(pid)) is doc
    assert window.doc_tabs.count() == 2


def test_library_search_and_delete(window):
    window.library.add_palette("Ocean", ["#0077BE"])
    window.library.add_palette("Forest", ["#228B22"])
    panel = window.panels["library"]
    panel.search.setText("for")
    assert panel.list.count() == 1
    panel.search.setText("#0077be")
    assert panel.list.count() == 1 and panel.selected() is None
    panel.list.setCurrentRow(0)
    panel.confirm_delete = lambda name: False
    panel.delete_selected()
    assert len(window.library.palettes()) == 2
    panel.confirm_delete = lambda name: True
    panel.delete_selected()
    assert [p.name for p in window.library.palettes()] == ["Forest"]


def test_import_files_to_library(window, tmp_path, monkeypatch):
    json_path = tmp_path / "a.json"
    json_path.write_text(colorize_json.dumps("From JSON", ["#010203"]), encoding="utf-8")
    ase_path = tmp_path / "b.ase"
    ase_path.write_bytes(write_ase("From ASE", ["#040506"]))
    bad = tmp_path / "c.json"
    bad.write_text("{}", encoding="utf-8")
    warnings = []
    monkeypatch.setattr("colorize.ui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    added = window.import_files_to_library([str(json_path), str(ase_path), str(bad)])
    assert added == 2
    assert {p.name for p in window.library.palettes()} == {"From JSON", "From ASE"}
    assert "c.json" in warnings[0]
    assert window.panels["library"].list.count() == 2


# ------------------------------------------------------------------ recent


def test_open_recent_menu(window, tmp_path, monkeypatch):
    path = tmp_path / "recent.json"
    path.write_text(colorize_json.dumps("Recent", ["#ABCDEF"]), encoding="utf-8")
    window.open_file(str(path))
    window._rebuild_recent_menu()
    entries = [a for a in window.recent_menu.actions() if a.text() == "recent.json"]
    assert entries and entries[0].toolTip() == str(path.resolve())

    window.close_document()
    entries[0].trigger()
    assert window.current_document().palette.name == "Recent"

    path.unlink()
    warnings = []
    monkeypatch.setattr("colorize.ui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    window._open_recent(str(path.resolve()))
    assert warnings and str(path.resolve()) not in window.library.recent_files()

    window.actions["clear_recent"].trigger()
    assert window.library.recent_files() == []
