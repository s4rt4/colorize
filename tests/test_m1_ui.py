import json
import time

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtWidgets import QComboBox

from colorize.core.color import to_oklch
from colorize.core.gamut import MAX_SRGB_CHROMA, in_srgb_gamut
from colorize.core.harmony import RULES
from colorize.ui.color_picker import ColorPickerDialog
from colorize.ui.color_render import wheel_image


@pytest.fixture
def harmony_ui(window, qtbot):
    window.docks["harmony"].setAsCurrentTab()
    panel = window.panels["harmony"]
    qtbot.waitUntil(lambda: panel.wheel.isVisible() and panel.wheel.width() > 100)
    return panel


def angle_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ------------------------------------------------------------------ wheel


def test_click_on_disc_moves_base(harmony_ui, qtbot):
    wheel, model = harmony_ui.wheel, harmony_ui._model
    target = wheel.point_for(0.1, 200)
    qtbot.mouseClick(wheel, Qt.MouseButton.LeftButton, pos=target.toPoint())
    _, chroma, hue = model.base
    assert angle_distance(hue, 200) < 2
    assert chroma == pytest.approx(0.1, abs=0.005)


def test_dragging_a_secondary_handle_rotates_the_set(harmony_ui, qtbot, window):
    wheel, model = harmony_ui.wheel, harmony_ui._model
    model.set_rule("complementary")
    model.edit_base(chroma=0.1, hue=30)
    other = 1 - model.harmony.base_index
    start = wheel.point_for(0.1, model.harmony.colors[other][2]).toPoint()
    end = wheel.point_for(0.1, 90).toPoint()
    qtbot.mousePress(wheel, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wheel, end)
    qtbot.mouseRelease(wheel, Qt.MouseButton.LeftButton, pos=end)
    assert angle_distance(model.harmony.colors[other][2], 90) < 2
    assert angle_distance(model.base[2], 270) < 2


def test_rule_combos_stay_in_sync(window, harmony_ui):
    options_combo = next(
        c for c in window.options_bar.findChildren(QComboBox) if c.count() == len(RULES) and c is not harmony_ui.rule
    )
    harmony_ui.rule.setCurrentIndex(RULES.index("triadic"))
    assert window.harmony.rule == "triadic"
    assert options_combo.currentIndex() == RULES.index("triadic")
    options_combo.setCurrentIndex(RULES.index("monochromatic"))
    assert harmony_ui.rule.currentIndex() == RULES.index("monochromatic")
    assert len(window.harmony.mapped) == 5


def test_sliders_edit_base(harmony_ui):
    harmony_ui.lightness.setValue(400)
    harmony_ui.chroma.setValue(50)
    lightness, chroma, _ = harmony_ui._model.base
    assert lightness == pytest.approx(0.4)
    assert chroma == pytest.approx(0.05)
    assert harmony_ui.lightness_value.text() == "40%"


def test_out_of_gamut_colors_are_flagged(harmony_ui):
    model = harmony_ui._model
    model.set_rule("triadic")
    model.edit_base(lightness=0.7, chroma=MAX_SRGB_CHROMA, hue=140)
    flagged = [m for m in model.mapped if not m.in_gamut]
    assert flagged
    assert not harmony_ui.gamut_note.isHidden()
    for mapped in flagged:
        assert in_srgb_gamut(*to_oklch(mapped.hex))
    model.edit_base(chroma=0.05)
    assert harmony_ui.gamut_note.isHidden()


def test_swatch_click_sets_foreground_and_use_fg_sets_base(window, harmony_ui, qtbot):
    strip = harmony_ui.swatches
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton, pos=strip.cell_rect(1).center())
    assert window.state.foreground == window.harmony.mapped[1].hex
    window.state.set_foreground("#F78154")
    window.harmony.set_base_hex(window.state.foreground)
    assert window.harmony.base_mapped.hex == "#F78154"


def test_add_harmony_is_one_undo_step(window):
    window.harmony.set_rule("tetradic")
    doc = window.current_document()
    before = len(doc.palette)
    window.actions["add_harmony"].trigger()
    assert len(doc.palette) == before + 4
    assert doc.palette.colors[-4:] == tuple(window.harmony.hexes())
    window.undo_action.trigger()
    assert len(doc.palette) == before


def test_harmony_tool_opens_the_panel(window):
    window.docks["harmony"].toggleView(False)
    window.tool_actions["harmony"].trigger()
    assert not window.docks["harmony"].isClosed()


def test_wheel_meets_30_fps(harmony_ui, qtbot):
    """Plan M1 criterion: wheel >= 30 fps while dragging (33 ms per frame)."""
    wheel = harmony_ui.wheel
    budget = 1 / 30
    start = time.perf_counter()
    for i in range(10):
        wheel_image(320, 1.0, 0.3 + i * 0.05, wheel._theme.color("bg_panel"))
    assert (time.perf_counter() - start) / 10 < budget, "re-rendering the wheel is too slow"

    center = wheel.rect().center()
    qtbot.mousePress(wheel, Qt.MouseButton.LeftButton, pos=center)
    frames = 30
    start = time.perf_counter()
    for i in range(frames):
        qtbot.mouseMove(wheel, center + QPointF(60 + i, 20 - i).toPoint())
        wheel.repaint()
    elapsed = (time.perf_counter() - start) / frames
    qtbot.mouseRelease(wheel, Qt.MouseButton.LeftButton, pos=center)
    assert elapsed < budget, f"{elapsed * 1000:.1f} ms per drag frame"


# ----------------------------------------------------------------- picker


def test_picker_fields_and_gamut_fit(qtbot, theme):
    dialog = ColorPickerDialog(theme, "#3D6A9E")
    qtbot.addWidget(dialog)
    assert dialog.hex_field.text() == "#3D6A9E"
    assert dialog.gamut_button.isHidden()

    dialog.set_lch(0.7, 0.3, 140)
    assert not dialog.gamut_button.isHidden()
    assert in_srgb_gamut(*to_oklch(dialog.color_hex()))
    dialog.fit_to_gamut()
    lightness, chroma, hue = dialog.lch
    assert dialog.gamut_button.isHidden()
    assert (lightness, hue) == (pytest.approx(0.7), pytest.approx(140))
    assert 0.1 < chroma < 0.3

    dialog.hex_field.setText("f80")
    dialog.hex_field.editingFinished.emit()
    assert dialog.color_hex() == "#FF8800"
    dialog.preview.revert.emit()
    assert dialog.color_hex() == "#3D6A9E"


def test_picker_plane_and_hue_strip(qtbot, theme):
    dialog = ColorPickerDialog(theme, "#808080")
    qtbot.addWidget(dialog)
    dialog.show()
    strip = dialog.hue_strip
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton, pos=strip.rect().center())
    assert dialog.lch[2] == pytest.approx(180, abs=2)
    plane = dialog.plane
    qtbot.mouseClick(plane, Qt.MouseButton.LeftButton, pos=plane.rect().topLeft() + QPoint(1, 1))
    assert dialog.lch[0] == pytest.approx(1.0, abs=0.01) and dialog.lch[1] == pytest.approx(0.0, abs=0.002)


# ------------------------------------------------------------------ files


def test_save_then_open_round_trip(window, tmp_path, monkeypatch):
    path = tmp_path / "brand"
    monkeypatch.setattr(
        "colorize.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (str(path), "")
    )
    doc = window.current_document()
    window.actions["add_fg"].trigger()
    assert doc.is_modified
    window.actions["save"].trigger()
    saved = tmp_path / "brand.json"
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["format"] == "colorize.palette"
    assert [c["hex"] for c in data["colors"]] == list(doc.palette.colors)
    assert not doc.is_modified
    assert "*" not in window.doc_tabs.tabText(0)

    window.close_document()
    opened = window.open_file(str(saved))
    assert opened.palette.colors == tuple(c["hex"] for c in data["colors"])
    assert opened.path == str(saved)
    assert window.open_file(str(saved)) is opened  # already open: just focused
    assert window.doc_tabs.count() == 1


def test_save_again_does_not_ask_for_a_name(window, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "colorize.ui.main_window.QFileDialog.getSaveFileName",
        lambda *a, **k: calls.append(1) or (str(tmp_path / "p.json"), ""),
    )
    window.save_document()
    window.actions["add_fg"].trigger()
    window.save_document()
    assert len(calls) == 1


def test_open_bad_file_warns(window, tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    warnings = []
    monkeypatch.setattr("colorize.ui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    assert window.open_file(str(bad)) is None
    assert "not a Colorize palette" in warnings[0]


def test_unsaved_close_prompt(window, tmp_path, monkeypatch):
    window.actions["add_fg"].trigger()
    window.ask_save_changes = lambda doc: "cancel"
    assert window.close_document() is False
    assert window.doc_tabs.count() == 1

    monkeypatch.setattr(
        "colorize.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (str(tmp_path / "x.json"), "")
    )
    window.ask_save_changes = lambda doc: "save"
    assert window.close_document() is True
    assert (tmp_path / "x.json").exists()


def test_window_close_can_be_cancelled(window):
    window.actions["add_fg"].trigger()
    window.ask_save_changes = lambda doc: "cancel"
    assert window.close() is False
    assert window.isVisible()
    window.ask_save_changes = lambda doc: "discard"


def test_lightness_drag_previews_then_sharpens(harmony_ui, qtbot, monkeypatch):
    wheel = harmony_ui.wheel
    monkeypatch.setattr(wheel, "devicePixelRatioF", lambda: 2.0)
    wheel.repaint()
    harmony_ui.lightness.setValue(300)
    wheel.repaint()
    assert wheel._cache_key[1] == 1.0  # fast 1x render while lightness is moving
    qtbot.waitUntil(lambda: not wheel._preview, timeout=2000)
    wheel.repaint()
    assert wheel._cache_key[1] == 2.0


def test_ryb_wheel_mode(harmony_ui, qtbot):
    model, wheel = harmony_ui._model, harmony_ui.wheel
    model.set_rule("complementary")
    model.set_base_hex("#FF0000")
    harmony_ui.wheel_kind.setCurrentIndex(harmony_ui.wheel_kind.findData("ryb"))
    assert model.wheel == "ryb"
    complement_hue = model.harmony.colors[1][2]
    assert 135 < complement_hue < 150  # green, not the cyan of the OKLCH wheel
    wheel.repaint()
    assert wheel._cache_key[-1] == "ryb"
    # dragging still lands the dragged handle under the cursor on the RYB wheel
    target = wheel.point_for(0.12, model.harmony.colors[1][2])
    qtbot.mousePress(wheel, Qt.MouseButton.LeftButton, pos=wheel.point_for(model.base[1], model.base[2]).toPoint())
    qtbot.mouseMove(wheel, target.toPoint())
    qtbot.mouseRelease(wheel, Qt.MouseButton.LeftButton, pos=target.toPoint())
    assert (wheel.point_for(model.base[1], model.base[2]) - target).manhattanLength() < 4
