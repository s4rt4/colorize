import pytest

from colorize.model.app_state import AppState
from colorize.model.palette import Document, Palette


@pytest.fixture
def doc(qapp):
    return Document(Palette("Test", ["#111111", "#222222", "#333333"]))


def test_add_undo_redo(doc):
    doc.add_color("#abcdef")
    assert doc.palette.colors[-1] == "#ABCDEF"
    assert doc.selected == 3
    assert doc.is_modified
    doc.undo_stack.undo()
    assert len(doc.palette) == 3
    assert not doc.is_modified
    doc.undo_stack.redo()
    assert doc.palette.colors[-1] == "#ABCDEF"


def test_remove_restores_position_and_selection(doc):
    doc.remove_color(1)
    assert doc.palette.colors == ("#111111", "#333333")
    assert doc.selected == 1
    doc.undo_stack.undo()
    assert doc.palette.colors == ("#111111", "#222222", "#333333")
    assert doc.selected == 1


def test_remove_last_swatch_clears_selection(qapp):
    doc = Document(Palette("One", ["#123456"]))
    doc.remove_color(0)
    assert doc.selected == -1


def test_consecutive_edits_of_same_swatch_merge(doc):
    doc.set_color(0, "#AA0000")
    doc.set_color(0, "#BB0000")
    doc.set_color(0, "#CC0000")
    assert doc.undo_stack.count() == 1
    doc.undo_stack.undo()
    assert doc.palette.color(0) == "#111111"


def test_edit_to_same_color_is_not_recorded(doc):
    doc.set_color(0, "#111111")
    assert doc.undo_stack.count() == 0


def test_move_and_undo(doc):
    doc.move_color(0, 2)
    assert doc.palette.colors == ("#222222", "#333333", "#111111")
    assert doc.selected == 2
    doc.undo_stack.undo()
    assert doc.palette.colors == ("#111111", "#222222", "#333333")


def test_rename_undo(doc):
    doc.rename("  Brand  ")
    assert doc.palette.name == "Brand"
    doc.undo_stack.undo()
    assert doc.palette.name == "Test"
    doc.rename("")
    assert doc.undo_stack.count() == 1  # blank name was ignored, only the undone rename remains


def test_app_state_colors(qapp):
    state = AppState()
    state.set_foreground("f00")
    assert state.foreground == "#FF0000"
    state.swap_colors()
    assert (state.foreground, state.background) == ("#FFFFFF", "#FF0000")
    state.reset_colors()
    assert (state.foreground, state.background) == ("#000000", "#FFFFFF")
    with pytest.raises(ValueError):
        state.set_tool("lasso")
