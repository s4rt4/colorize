import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication


@pytest.fixture
def gradient(window, qtbot):
    window.docks["gradient"].setAsCurrentTab()
    panel = window.panels["gradient"]
    qtbot.waitUntil(lambda: panel.steps.width() > 50)
    return panel


def test_follows_foreground_and_background(window, gradient):
    window.state.set_foreground("#0000FF")
    window.state.set_background("#FFFF00")
    assert gradient.colors()[0] == "#0000FF" and gradient.colors()[-1] == "#FFFF00"
    assert gradient.steps.colors == gradient.colors()
    assert gradient.css.text() == "linear-gradient(90deg in oklab, #0000ff, #ffff00)"
    window.actions["swap_colors"].trigger()
    assert gradient.colors()[0] == "#FFFF00"


def test_space_and_steps(gradient):
    gradient.count.setValue(3)
    assert len(gradient.colors()) == 3
    gradient.space.setCurrentIndex(gradient.space.findData("srgb"))
    assert gradient.compare.isHidden()
    assert "in oklab" not in gradient.css.text()


def test_click_copies_hex(gradient, qtbot):
    qtbot.mouseClick(gradient.steps, Qt.MouseButton.LeftButton, pos=gradient.steps.cell_rect(1).center())
    assert QGuiApplication.clipboard().text() == gradient.colors()[1]


def test_add_and_new_palette(window, gradient):
    doc = window.current_document()
    before = len(doc.palette)
    gradient.add_button.click()
    assert len(doc.palette) == before + gradient.count.value()
    assert doc.undo_stack.undoText() == "Add Gradient"
    gradient.new_button.click()
    assert list(window.current_document().palette.colors) == gradient.colors()
