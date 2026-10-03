import pytest

from colorize.core.cmyk import SYSTEM_PROFILE_DIR

SWOP = SYSTEM_PROFILE_DIR / "RSWOP.icm"
needs_swop = pytest.mark.skipif(not SWOP.exists(), reason="Windows SWOP profile not available")


@pytest.fixture
def print_panel(window, qtbot):
    dock = window.docks["print"]
    dock.toggleView(True)  # not part of the startup (Essentials) workspace
    dock.setAsCurrentTab()
    qtbot.waitUntil(window.panels["print"].isVisible)
    doc = window.current_document()
    for i in reversed(range(len(doc.palette))):
        doc.remove_color(i)
    doc.add_colors(["#3D6A9E", "#0000FF", "#F2C14E", "#00FF00"])
    return window.panels["print"]


@needs_swop
def test_proofs_the_active_palette(print_panel):
    assert "Swop" in print_panel.profile.currentText()
    assert print_panel.table.topLevelItemCount() == 4
    noticeable = [m.hex for m in print_panel.matches if m.shift == "noticeable"]
    assert noticeable == ["#0000FF", "#00FF00"]
    assert "2 of 4 colors are outside what" in print_panel.summary.text()
    assert print_panel.table.topLevelItem(1).text(2).startswith("⚠")
    assert print_panel.fit_button.isEnabled()


@needs_swop
def test_use_print_matches_is_one_undo_step(window, print_panel):
    doc = window.current_document()
    expected = [m.print_hex if m.shift == "noticeable" else m.hex for m in print_panel.matches]
    print_panel.fit_button.click()
    assert list(doc.palette.colors) == expected
    assert doc.undo_stack.undoText() == "Use Print Colors"
    assert all(m.shift != "noticeable" for m in print_panel.matches)
    assert "All colors print close" in print_panel.summary.text()
    window.undo_action.trigger()
    assert list(doc.palette.colors) == ["#3D6A9E", "#0000FF", "#F2C14E", "#00FF00"]


def test_approximate_mode(print_panel, settings):
    index = print_panel.profile.findData("approximate")
    print_panel.profile.setCurrentIndex(index)
    print_panel.profile.activated.emit(index)
    assert settings.value("print/profile") == "approximate"
    assert not print_panel.intent.isEnabled()
    assert print_panel.table.topLevelItem(1).text(1) == "100 100 0 0"  # #0000FF, naive
    assert "Approximate CMYK" in print_panel.summary.text()
    assert not print_panel.fit_button.isEnabled()


@needs_swop
def test_load_profile_and_reject_non_cmyk(print_panel, settings, monkeypatch, tmp_path):
    import shutil

    copy = tmp_path / "MySwop.icm"
    shutil.copy(SWOP, copy)
    assert print_panel.load_profile(str(copy))
    assert print_panel.profile.currentData() == str(copy)
    assert settings.value("print/customProfiles", type=list)[0] == str(copy)

    bad = tmp_path / "rgb.icc"
    bad.write_bytes(b"not a profile")
    warnings = []
    monkeypatch.setattr("colorize.ui.print_panel.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    assert not print_panel.load_profile(str(bad))
    assert warnings and print_panel.profile.currentData() == str(copy)


def test_hidden_panel_does_no_proofing_work(window, monkeypatch):
    """Building proof transforms costs ~0.8 s; startup must not pay it."""
    calls = []
    monkeypatch.setattr("colorize.ui.print_panel.cached_proofer", lambda *a: calls.append(a))
    panel = window.panels["print"]
    assert not panel.isVisible()
    window.actions["add_fg"].trigger()
    assert calls == [] and panel.profile.count() == 0
