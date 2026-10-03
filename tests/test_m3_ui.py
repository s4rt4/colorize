import pytest
from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox

from colorize.core.contrast import passes


@pytest.fixture
def contrast(window, qtbot):
    window.tool_actions["contrast"].trigger()
    panel = window.panels["contrast"]
    qtbot.waitUntil(panel.isVisible)
    return panel


def test_contrast_panel_reports_wcag_and_apca(window, contrast):
    window.state.set_foreground("#777777")
    window.state.set_background("#FFFFFF")
    assert contrast.ratio.text() == "4.47:1"
    statuses = [label.text() for label in contrast.wcag_labels]
    assert "✕ AA" in statuses and "✓ AA Large" in statuses and "✓ UI 3:1" in statuses
    assert contrast.lc.text().startswith("Lc ")


def test_contrast_suggestions_fix_the_pair(window, contrast, qtbot):
    window.state.set_foreground("#7A8FB0")
    window.state.set_background("#FFFFFF")
    visible = [b for b in contrast.suggestions if not b.isHidden()]
    assert visible
    qtbot.mouseClick(visible[0], Qt.MouseButton.LeftButton)
    assert passes("wcag", "aa", window.state.foreground, "#FFFFFF")
    assert contrast.fix_status.text().startswith("✓ Passes")
    assert all(b.isHidden() for b in contrast.suggestions)


def test_method_and_target_stay_in_sync(window, contrast):
    options = [c for c in window.options_bar.findChildren(QComboBox) if c.findData("apca") >= 0]
    contrast.method.setCurrentIndex(contrast.method.findData("apca"))
    assert window.state.contrast_method == "apca"
    assert window.state.contrast_target == "lc75"  # target resets to the method's default
    assert options[0].currentData() == "apca"
    assert contrast.target.currentData() == "lc75"
    contrast.target.setCurrentIndex(contrast.target.findData("lc60"))
    assert window.state.contrast_target == "lc60"


def test_swap_with_x_updates_contrast(window, contrast):
    window.state.set_foreground("#000000")
    window.state.set_background("#FFFF00")
    lc_before = contrast.lc.text()
    window.actions["swap_colors"].trigger()
    assert contrast.lc.text() != lc_before  # APCA depends on polarity
    assert contrast.ratio.text() == "19.55:1"


def test_cvd_panel_flags_red_green_for_deutans(window, qtbot):
    window.tool_actions["cvd"].trigger()
    panel = window.panels["cvd"]
    doc = window.current_document()
    for i in reversed(range(len(doc.palette))):
        doc.remove_color(i)
    doc.add_colors(["#D62728", "#2CA02C", "#1F77B4"])
    assert "hard to tell apart" in panel.conflicts("deutan")
    assert "#D62728 and #2CA02C" in panel.rows["deutan"][3].toolTip()
    assert "distinguishable" in panel.conflicts("tritan")
    window.close_document()
    assert not panel.empty.isHidden()


def test_proof_colors_simulates_canvases(window, tmp_path, qtbot):
    view = window.current_view()
    assert view.grid._filter is None
    window.state.set_cvd(kind="protan", severity=1.0)
    window.actions["proof"].trigger()
    assert window.state.proof
    assert view.grid._filter is not None
    assert window.proof_label.text() == "Proof: Protanopia"
    assert view.grid._filter("#FF0000") != "#FF0000"

    path = tmp_path / "red.png"
    Image.new("RGB", (40, 30), (220, 30, 30)).save(path)
    image = window.open_file(str(path))
    shown = image.displayed_image().pixelColor(5, 5).name().upper()
    assert shown != "#DC1E1E"
    assert image.sample(5, 5) == "#DC1E1E"  # the eyedropper still reads the original pixels
    assert image.strip._filter is not None

    window.actions["proof"].trigger()
    assert not window.state.proof
    assert image.displayed_image().pixelColor(5, 5).name().upper() == "#DC1E1E"
    assert window.proof_label.isHidden()


def test_cvd_radio_selects_proof_type(window):
    panel = window.panels["cvd"]
    panel.rows["tritan"][0].setChecked(True)
    assert window.state.cvd_type == "tritan"
    panel.severity.setValue(40)
    assert window.state.cvd_severity == pytest.approx(0.4)
    assert panel.rows["tritan"][1].text() == "Tritanomaly 40%"


def test_alt_click_with_eyedropper_sets_background(window, qtbot):
    view = window.current_view()
    window.tool_actions["eyedropper"].trigger()
    qtbot.mouseClick(
        view.grid, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, view.grid.cell_rect(2).center()
    )
    assert window.state.background == view.document.palette.color(2)
