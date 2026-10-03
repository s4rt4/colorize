import pytest
from PIL import Image
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QColor, QDropEvent, QGuiApplication, QImage, QPixmap

from colorize.ui.image_view import ImageView
from colorize.ui.screen_sampler import ScreenOverlay, ScreenSampler, device_pixel
from tests.icc_util import matrix_profile
from tests.test_core_m2 import BLOCKS, block_image


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "stripes.png"
    Image.fromarray(block_image()).save(path)
    return path


@pytest.fixture
def image_view(window, image_path, qtbot) -> ImageView:
    view = window.open_file(str(image_path))
    qtbot.waitUntil(lambda: view.isVisible() and view.canvas.width() > 0)
    return view


def canvas_point(view: ImageView, fx: float, fy: float) -> QPoint:
    rect = view.image_rect()
    return QPointF(rect.x() + fx * rect.width(), rect.y() + fy * rect.height()).toPoint()


# ------------------------------------------------------------- extraction


def test_open_image_extracts_palette(window, image_view):
    assert isinstance(window.current_tab(), ImageView)
    window.state.set_extract_count(4)
    image_view.extract()
    assert image_view.colors == list(BLOCKS)
    assert image_view.strip.colors == list(BLOCKS)
    assert len(image_view.markers) == 4
    assert window.doc_tabs.tabText(window.doc_tabs.currentIndex()).startswith("stripes.png @ ")
    assert "no embedded profile" in image_view.info.text()


def test_color_count_change_reextracts(window, image_view, qtbot):
    window.state.set_extract_count(2)
    qtbot.waitUntil(lambda: len(image_view.colors) == 2)
    assert image_view.count.value() == 2


def test_new_palette_from_image_is_undoable(window, image_view):
    window.state.set_extract_count(4)
    image_view.extract()
    image_view.new_button.click()
    doc = window.current_document()
    assert window.current_view() is not None
    assert doc.palette.name == "stripes"
    assert list(doc.palette.colors) == list(BLOCKS)
    assert doc.is_modified
    window.undo_action.trigger()
    assert len(doc.palette) == 0


def test_add_to_swatches_targets_last_palette(window, image_view):
    palette = window.documents()[0]
    before = len(palette.palette)
    assert window.current_document() is palette  # image tab active, palette still targeted
    window.state.set_extract_count(4)
    image_view.extract()
    image_view.add_button.click()
    assert len(palette.palette) == before + 4
    assert window.undo_action.isEnabled()  # undo acts on the targeted palette
    window.undo_action.trigger()
    assert len(palette.palette) == before
    assert "adding to “Untitled-1”" in window.info_label.text()


def test_p3_image_reports_conversion(window, tmp_path):
    path = tmp_path / "phone.png"
    Image.new("RGB", (16, 16), (150, 110, 80)).save(path, icc_profile=matrix_profile("display-p3", "Display P3"))
    view = window.open_file(str(path))
    assert "Display P3 → sRGB" in view.info.text()
    assert view.colors[0] != "#966E50"


def test_opening_the_same_image_focuses_it(window, image_path):
    first = window.open_file(str(image_path))
    window.doc_tabs.setCurrentIndex(0)
    assert window.open_file(str(image_path)) is first
    assert window.doc_tabs.count() == 2


def test_bad_image_warns(window, tmp_path, monkeypatch):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"nope")
    warnings = []
    monkeypatch.setattr("colorize.ui.main_window.QMessageBox.warning", lambda *a, **k: warnings.append(a[2]))
    assert window.open_file(str(bad)) is None
    assert warnings


def test_closing_image_needs_no_prompt(window, image_view):
    window.ask_save_changes = lambda doc: pytest.fail("images should not prompt")
    assert window.close_document()
    assert window.current_view() is not None


def test_drop_opens_files(window, image_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(image_path))])
    event = QDropEvent(QPointF(50, 50), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    window.dropEvent(event)
    assert isinstance(window.current_tab(), ImageView)


# ---------------------------------------------------------------- sampling


def test_eyedropper_on_image(window, image_view, qtbot):
    window.tool_actions["eyedropper"].trigger()
    qtbot.mouseClick(image_view.canvas, Qt.MouseButton.LeftButton, pos=canvas_point(image_view, 0.1, 0.5))
    assert window.state.foreground == BLOCKS[0]
    qtbot.mouseClick(image_view.canvas, Qt.MouseButton.LeftButton, pos=canvas_point(image_view, 0.95, 0.5))
    assert window.state.foreground == BLOCKS[3]


def test_eyedropper_sample_size_averages(window, image_view):
    edge_x = 40  # first stripe ends at x = 40
    window.state.set_sample_size(1)
    assert image_view.sample(edge_x - 1, 10) == BLOCKS[0]
    window.state.set_sample_size(3)
    mixed = image_view.sample(edge_x, 10)
    assert mixed not in BLOCKS


def test_dragging_a_marker_resamples(window, image_view, qtbot):
    window.state.set_extract_count(4)
    image_view.extract()
    window.tool_actions["select"].trigger()
    start = image_view.marker_point(0).toPoint()
    end = canvas_point(image_view, 0.97, 0.5)
    qtbot.mousePress(image_view.canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(image_view.canvas, end)
    qtbot.mouseRelease(image_view.canvas, Qt.MouseButton.LeftButton, pos=end)
    assert image_view.colors[0] == BLOCKS[3]
    assert image_view.markers[0].x() > 0.9


def test_eyedropper_on_palette_swatch(window, qtbot):
    window.doc_tabs.setCurrentIndex(0)
    view = window.current_view()
    doc = view.document
    doc.select(0)
    window.tool_actions["eyedropper"].trigger()
    qtbot.mouseClick(view.grid, Qt.MouseButton.LeftButton, pos=view.grid.cell_rect(3).center())
    assert window.state.foreground == doc.palette.color(3)
    assert doc.selected == 0


def test_options_bar_controls_are_live(window):
    window.tool_actions["eyedropper"].trigger()
    window.state.set_sample_size(5)
    window.state.set_extract_count(9)
    from PyQt6.QtWidgets import QComboBox, QSpinBox

    combos = [c for c in window.options_bar.findChildren(QComboBox) if c.count() == 3 and c.itemText(0) == "Point Sample"]
    spins = [s for s in window.options_bar.findChildren(QSpinBox)]
    assert combos[0].currentIndex() == 2 and combos[0].isEnabled()
    assert spins[0].value() == 9 and spins[0].isEnabled()


# ------------------------------------------------------------ screen picker


def fake_capture(width: int, height: int, dpr: float, fill: str, marks: dict) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(fill))
    for (x, y), color in marks.items():
        image.setPixelColor(x, y, QColor(color))
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
def test_device_pixel_mapping(dpr):
    assert device_pixel(QPointF(10, 20), dpr, 4000, 4000) == (int(10 * dpr), int(20 * dpr))
    assert device_pixel(QPointF(-5, 99999), dpr, 100, 100) == (0, 99)


def test_two_monitors_with_different_scaling(qtbot, monkeypatch):
    """Plan M2 criterion: each screen samples the device pixel under the cursor."""
    screen = QGuiApplication.primaryScreen()
    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: [screen, screen]))
    captures = iter(
        [
            fake_capture(1920, 1080, 1.25, "#101010", {(125, 250): "#FF0000"}),  # logical (100, 200) at 125%
            fake_capture(3840, 2160, 2.0, "#202020", {(200, 400): "#00FF00"}),  # logical (100, 200) at 200%
        ]
    )
    sampler = ScreenSampler(grab=lambda _screen: next(captures))
    picked = []
    sampler.picked.connect(picked.append)
    sampler.start(sample_size=1)
    first, second = sampler.overlays
    assert first.color_at(QPointF(100, 200)) == "#FF0000"
    assert second.color_at(QPointF(100, 200)) == "#00FF00"
    assert first.color_at(QPointF(101, 200)) == "#101010"
    qtbot.mouseClick(second, Qt.MouseButton.LeftButton, pos=QPoint(100, 200))
    assert picked == ["#00FF00"]
    assert not sampler.active


def test_screen_sampler_cancel(qtbot):
    sampler = ScreenSampler(grab=lambda _s: fake_capture(200, 100, 1.0, "#123456", {}))
    picked = []
    sampler.picked.connect(picked.append)
    sampler.start()
    overlay = sampler.overlays[0]
    qtbot.keyClick(overlay, Qt.Key.Key_Escape)
    assert picked == [] and not sampler.active


def test_screen_sample_averages(qtbot):
    marks = {(x, y): "#FFFFFF" for x in range(9, 12) for y in range(9, 12)}
    marks[(10, 10)] = "#000000"
    sampler = ScreenSampler(grab=lambda _s: fake_capture(50, 50, 1.0, "#808080", marks))
    sampler.start(sample_size=3)
    overlay: ScreenOverlay = sampler.overlays[0]
    expected = "#F2F2F2"  # 8 white + 1 black: linear 8/9 = 0.889 -> sRGB 242
    assert overlay.color_at(QPointF(10, 10)) == expected
    sampler.cancel()


def test_sample_screen_action_sets_foreground(window, monkeypatch):
    monkeypatch.setattr(window.screen_sampler, "_grab", lambda _s: fake_capture(100, 100, 1.0, "#ABCDEF", {}))
    window.actions["sample_screen"].trigger()
    window.screen_sampler.overlays[0].mousePressEvent(
        type("E", (), {"button": lambda self: Qt.MouseButton.LeftButton, "position": lambda self: QPointF(5, 5)})()
    )
    assert window.state.foreground == "#ABCDEF"


# --------------------------------------------------------- reorder / sort


def test_drag_in_strip_reorders_colors_and_markers(window, image_view, qtbot):
    window.state.set_extract_count(4)
    image_view.extract()
    colors, markers = image_view.colors, image_view.markers
    strip = image_view.strip
    start = strip.cell_rect(0).center()
    end = QPoint(strip.width() - 2, start.y())
    qtbot.mousePress(strip, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(strip, start + QPoint(20, 0))
    qtbot.mouseMove(strip, end)
    qtbot.mouseRelease(strip, Qt.MouseButton.LeftButton, pos=end)
    assert image_view.colors == colors[1:] + colors[:1]
    assert image_view.markers == markers[1:] + markers[:1]
    assert strip.colors == image_view.colors
    assert window.state.foreground != colors[0]  # a drag is not a click


def test_click_in_strip_sets_foreground(window, image_view, qtbot):
    strip = image_view.strip
    qtbot.mouseClick(strip, Qt.MouseButton.LeftButton, pos=strip.cell_rect(1).center())
    assert window.state.foreground == image_view.colors[1]


def test_sort_orders(window, image_view):
    from colorize.core.color import to_oklch

    window.state.set_extract_count(4)
    image_view.extract()
    image_view.sort("light")
    lightness = [to_oklch(c)[0] for c in image_view.colors]
    assert lightness == sorted(lightness, reverse=True)
    image_view.sort("dark")
    assert [to_oklch(c)[0] for c in image_view.colors] == sorted(lightness)
    image_view.sort("common")
    assert image_view.colors == list(BLOCKS)
    image_view.sort("hue")
    neutral = "#F1FAEE"  # near-white, sorted after the chromatic colors
    assert image_view.colors[-1] == neutral
    image_view.new_button.click()
    assert list(window.current_document().palette.colors) == image_view.colors


def test_most_common_disabled_after_manual_resample(window, image_view, qtbot):
    window.tool_actions["select"].trigger()
    assert image_view.sort_actions["common"].isEnabled()
    start = image_view.marker_point(0).toPoint()
    qtbot.mousePress(image_view.canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(image_view.canvas, start + QPoint(3, 3))
    qtbot.mouseRelease(image_view.canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(3, 3))
    assert not image_view.sort_actions["common"].isEnabled()
    image_view.sort("light")  # other sorts still work without shares
