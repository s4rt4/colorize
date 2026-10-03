import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImage

from colorize.ui.mockup_view import MockupView


@pytest.fixture
def mockup(window, qtbot) -> MockupView:
    view = window.open_mockup()
    qtbot.waitUntil(lambda: view.isVisible() and view.canvas.width() > 0)
    return view


def test_open_and_focus(window, mockup):
    assert window.current_tab() is mockup
    assert window.doc_tabs.tabText(window.doc_tabs.currentIndex()).startswith("Mockup – Untitled-1")
    window.doc_tabs.setCurrentIndex(0)
    assert window.open_mockup() is mockup
    assert window.current_document() is mockup.document  # palette commands still target the palette


def test_live_update_and_roles(window, mockup):
    before = mockup.svg
    doc = mockup.document
    doc.set_color(0, "#000000")
    assert mockup.svg != before
    assert mockup.roles.colors["background"] in doc.palette.colors or mockup.roles.colors["background"] == "#FFFFFF"
    assert "✓" in mockup.problems.text() or "⚠" in mockup.problems.text()


def test_templates_shuffle_dark_and_pin(window, mockup):
    mockup.template.setCurrentIndex(mockup.template.findData("dashboard"))
    assert "Overview" in mockup.svg
    primary = mockup.roles.colors["primary"]
    mockup.shuffle.click()
    assert mockup.roles.colors["primary"] != primary
    mockup.dark.setChecked(True)
    assert mockup.roles.colors["background"] != "#F2F2F2"
    mockup.set_role("accent", "#4D9078")
    assert mockup.roles.colors["accent"] == "#4D9078" and "accent" in mockup.overrides
    mockup.set_role("accent", None)
    assert "accent" not in mockup.overrides


def test_role_menu_lists_palette(mockup):
    mockup._fill_role_menu("primary")
    texts = [a.text() for a in mockup.role_buttons["primary"].menu().actions() if a.text()]
    assert texts[0] == "Automatic" and set(mockup.document.palette.colors) <= set(texts)


def test_export_svg_and_png(mockup, tmp_path):
    svg_path = mockup.export_svg(str(tmp_path / "m.svg"))
    assert (tmp_path / "m.svg").read_text(encoding="utf-8").startswith("<svg")
    png_path = mockup.export_png(str(tmp_path / "m.png"), scale=1.0)
    image = QImage(png_path)
    assert svg_path and image.size() == QSize(1200, 800)
    assert image.pixelColor(600, 400).alpha() == 255


def test_closing_the_palette_closes_its_mockup(window, mockup):
    window.doc_tabs.setCurrentIndex(0)
    window.close_document()
    assert not any(isinstance(window.doc_tabs.widget(i), MockupView) for i in range(window.doc_tabs.count()))


def test_zoom_actions_work_on_mockup(window, mockup):
    mockup.actual_size()
    window.actions["zoom_out"].trigger()
    assert mockup.zoom < 1.0
    assert window.zoom_label.text() == f"{round(mockup.zoom * 100)}%"
