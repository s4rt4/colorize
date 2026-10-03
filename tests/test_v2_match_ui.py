import pytest

from colorize.formats.swatch_files import write_ase


@pytest.fixture
def match_panel(window, qtbot):
    dock = window.docks["match"]
    dock.toggleView(True)
    dock.setAsCurrentTab()
    panel = window.panels["match"]
    qtbot.waitUntil(panel.isVisible)
    return panel


def test_css_book_matches_foreground_and_palette(window, match_panel):
    window.state.set_foreground("#FF6348")
    first = match_panel.foreground.topLevelItem(0)
    assert first.text(0).startswith("tomato") and float(first.text(1)) < 1
    assert match_panel.foreground.topLevelItemCount() == 5
    assert match_panel.palette.topLevelItemCount() == len(window.current_document().palette)


def test_double_click_sets_foreground(window, match_panel):
    window.state.set_foreground("#FF6348")
    item = match_panel.foreground.topLevelItem(0)
    match_panel.foreground.itemDoubleClicked.emit(item, 0)
    assert window.state.foreground == "#FF6347"


def test_use_book_colors_snaps_palette(window, match_panel):
    doc = window.current_document()
    before = list(doc.palette.colors)
    match_panel.use_button.click()
    css = {c.hex for c in match_panel.current_book().colors}
    assert all(c in css for c in doc.palette.colors)
    assert doc.undo_stack.undoText() == "Use CSS Named Colors"
    window.undo_action.trigger()
    assert list(doc.palette.colors) == before


def test_import_and_remove_a_book(window, match_panel, tmp_path):
    path = tmp_path / "spot.ase"
    path.write_bytes(write_ase("Spot Colors", ["#CC0000", "#0055AA"]))
    book_id = match_panel.import_book(str(path))
    assert match_panel.book.currentData() == book_id
    assert match_panel.book.currentText() == "Spot Colors (2)"
    window.state.set_foreground("#CD0102")
    assert match_panel.foreground.topLevelItem(0).text(0).startswith("#CC0000")
    match_panel.confirm_delete = lambda name: True
    match_panel.delete_book()
    assert window.library.books() == [] and match_panel.book.currentText().startswith("CSS")


def test_hidden_panel_does_no_matching(window, monkeypatch):
    panel = window.panels["match"]
    assert not panel.isVisible()
    monkeypatch.setattr(type(panel), "current_book", lambda self: pytest.fail("matched while hidden"))
    window.state.set_foreground("#123456")
    window.actions["add_fg"].trigger()
