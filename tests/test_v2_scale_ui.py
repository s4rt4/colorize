import pytest
from PyQt6.QtCore import Qt

from colorize.core.scale import SCALE_STEPS


@pytest.fixture
def scale(window, qtbot):
    window.docks["scale"].setAsCurrentTab()
    panel = window.panels["scale"]
    qtbot.waitUntil(lambda: panel.strip.width() > 100)
    return panel


def test_scale_panel_builds_from_foreground(window, scale):
    window.state.set_foreground("#E63946")
    scale.set_base(window.state.foreground)
    assert len(scale.colors()) == len(SCALE_STEPS)
    assert "#E63946" in scale.colors()
    assert "lands on" in scale.base_label.text()


def test_sliders_change_the_range(scale):
    before = scale.colors()
    scale.lightest.setValue(90)
    assert scale.colors() != before
    assert scale.lightest_value.text() == "90%"


def test_click_sets_foreground(window, scale, qtbot):
    qtbot.mouseClick(scale.strip, Qt.MouseButton.LeftButton, pos=scale.strip.cell_rect(0).center())
    assert window.state.foreground == scale.colors()[0]


def test_new_palette_and_export_with_scale_names(window, scale):
    scale.new_button.click()
    doc = window.current_document()
    assert list(doc.palette.colors) == scale.colors()
    assert doc.is_modified
    export = window.panels["export"]
    export.format.setCurrentIndex(export.format.findData("css"))
    export.naming.setCurrentIndex(export.naming.findData("scale"))
    text = export.preview.toPlainText()
    assert "-50: " in text and "-950: " in text
    window.undo_action.trigger()
    assert len(doc.palette) == 0
    assert export.naming.currentData() == "numbered"  # scale names need 11 colors


def test_add_scale_to_active_palette(window, scale):
    doc = window.current_document()
    before = len(doc.palette)
    scale.add_button.click()
    assert len(doc.palette) == before + len(SCALE_STEPS)
    assert doc.undo_stack.undoText() == "Add Scale"
