"""Image document: the picture with extracted-color markers, plus the palette footer.

Like Adobe Color's Extract Theme: each extracted color has a marker on the image at a
pixel of that color; drag a marker to re-sample it. The Eyedropper samples the image
directly (in sRGB, after the embedded profile was applied).
"""

import math
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from colorize.core.color import to_oklch
from colorize.core.cvd import simulate_rgb8
from colorize.core.extract import average_color, extract_palette
from colorize.core.image import LoadedImage, pixel_block, sample_pixels
from colorize.model.app_state import EXTRACT_COUNT_RANGE
from colorize.ui.navigation import CanvasNavigator, tool_cursor
from colorize.ui.widgets import ColorStrip

ZOOM_STEPS = (0.05, 0.1, 0.25, 0.33, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0, 8.0)
MARKER_RADIUS = 9
EXTRACT_DEBOUNCE_MS = 150
NEUTRAL_CHROMA = 0.03  # below this a color has no meaningful hue; Hue sort puts these last

SORTS = {
    "common": "Most Common",
    "light": "Light → Dark",
    "dark": "Dark → Light",
    "hue": "Hue",
    "chroma": "Most Vivid First",
}


def sort_key(order: str, hex_color: str, share: float):
    lightness, chroma, hue = to_oklch(hex_color)
    if order == "common":
        return -share
    if order == "light":
        return -lightness
    if order == "dark":
        return lightness
    if order == "chroma":
        return -chroma
    # hue: chromatic colors around the wheel, then neutrals light to dark
    return (1, -lightness) if chroma < NEUTRAL_CHROMA else (0, hue)


def to_qimage(image: LoadedImage) -> QImage:
    rgba = np.empty((image.height, image.width, 4), dtype=np.uint8)
    rgba[..., :3] = image.rgb
    rgba[..., 3] = 255 if image.alpha is None else image.alpha
    return QImage(rgba.data, image.width, image.height, 4 * image.width, QImage.Format.Format_RGBA8888).copy()


class _ImageCanvas(QWidget):
    def __init__(self, view):
        super().__init__()
        self._view = view
        self.setMouseTracking(True)

    def paintEvent(self, _event):
        self._view.paint_canvas(QPainter(self))

    def mousePressEvent(self, event):
        self._view.canvas_press(event)

    def mouseMoveEvent(self, event):
        self._view.canvas_move(event)

    def mouseReleaseEvent(self, _event):
        self._view.canvas_release()


class ImageView(QWidget):
    zoomChanged = pyqtSignal(float)
    colorsChanged = pyqtSignal()
    createPaletteRequested = pyqtSignal(str, list)  # palette name, colors
    addToPaletteRequested = pyqtSignal(list)

    def __init__(self, path, image: LoadedImage, state, theme, parent=None):
        super().__init__(parent)
        self.path = str(path)
        self.image = image
        self._state = state
        self._theme = theme
        self._qimage = to_qimage(image)
        self._proof_key = None
        self._proof_image: QImage | None = None
        self._pixels, self._positions = sample_pixels(image)
        self._colors: list[str] = []
        self._shares: list[float] = []
        self._markers: list[QPointF] = []  # fractions of image width/height
        self._drag_marker: int | None = None
        self._sampling = False
        self._sample_to_background = False
        self._zoom = 1.0
        self._fitted = False

        self.scroll = QScrollArea()
        self.scroll.setObjectName("canvas")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas = _ImageCanvas(self)
        self.scroll.setWidget(self.canvas)
        self.scroll.viewport().installEventFilter(self)
        self._navigator = CanvasNavigator(self.scroll, self.canvas, state, self.zoom_in, self.zoom_out)

        self.strip = ColorStrip(theme, 36, reorderable=True)
        self.strip.colorClicked.connect(state.set_foreground)
        self.strip.moved.connect(self.move_color)
        self.count = QSpinBox()
        self.count.setRange(*EXTRACT_COUNT_RANGE)
        self.count.setValue(state.extract_count)
        self.count.setToolTip("Number of colors to extract")
        self.count.valueChanged.connect(state.set_extract_count)
        self.info = QLabel(self._info_text())
        self.info.setProperty("role", "muted")
        self.new_button = QPushButton("New Palette")
        self.new_button.setToolTip("Create a palette document from these colors")
        self.new_button.clicked.connect(
            lambda: self.createPaletteRequested.emit(Path(self.path).stem, self.colors)
        )
        self.sort_button = QPushButton("Sort")
        self.sort_button.setToolTip("Reorder the colors (or drag them in the strip)")
        self.sort_menu = QMenu(self.sort_button)
        self.sort_actions = {}
        for key, label in SORTS.items():
            action = self.sort_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, k=key: self.sort(k))
            self.sort_actions[key] = action
        self.sort_button.setMenu(self.sort_menu)
        self.add_button = QPushButton("Add to Swatches")
        self.add_button.setToolTip("Add these colors to the active palette")
        self.add_button.clicked.connect(lambda: self.addToPaletteRequested.emit(self.colors))

        footer = QWidget()
        footer.setObjectName("panelFooter")
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Colors"))
        controls.addWidget(self.count)
        controls.addSpacing(8)
        controls.addWidget(self.info, 1)
        controls.addWidget(self.sort_button)
        controls.addWidget(self.add_button)
        controls.addWidget(self.new_button)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(8)
        footer_layout.addWidget(self.strip)
        footer_layout.addLayout(controls)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(footer)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(EXTRACT_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.extract)
        state.extractCountChanged.connect(self._on_count_changed)
        state.toolChanged.connect(self._update_cursor)
        theme.changed.connect(self._on_theme_changed)
        state.proofChanged.connect(self._update_proof)
        state.cvdChanged.connect(self._update_proof)
        self._update_proof()
        self._update_cursor()
        self._update_canvas_size()
        self.extract()

    # ----- data -----

    @property
    def title(self) -> str:
        return Path(self.path).name

    @property
    def colors(self) -> list[str]:
        return list(self._colors)

    @property
    def markers(self) -> list[QPointF]:
        return list(self._markers)

    def _info_text(self) -> str:
        size = f"{self.image.width} × {self.image.height} px"
        if self.image.profile is None:
            return f"{size} · no embedded profile, read as sRGB"
        if not self.image.profile_applied:
            return f"{size} · {self.image.profile} (could not be applied, read as sRGB)"
        return f"{size} · {self.image.profile} → sRGB"

    def extract(self) -> None:
        self._debounce.stop()
        results = extract_palette(self._pixels, self._state.extract_count)
        self._colors = [c.hex for c in results]
        self._shares = [c.share for c in results]
        self._markers = [QPointF(*self._positions[c.sample_index]) for c in results]
        self._refresh_colors()

    def move_color(self, src: int, dst: int) -> None:
        """Move one extracted color (with its marker and share) to position ``dst``."""
        order = list(range(len(self._colors)))
        order.insert(dst, order.pop(src))
        self._apply_order(order)

    def sort(self, order: str) -> None:
        shares = self._shares or [0.0] * len(self._colors)
        indices = sorted(range(len(self._colors)), key=lambda i: sort_key(order, self._colors[i], shares[i]))
        self._apply_order(indices)

    def _apply_order(self, order: list[int]) -> None:
        self._colors = [self._colors[i] for i in order]
        self._markers = [self._markers[i] for i in order]
        if self._shares:
            self._shares = [self._shares[i] for i in order]
        self._refresh_colors()

    def _on_count_changed(self, count: int) -> None:
        self.count.blockSignals(True)
        self.count.setValue(count)
        self.count.blockSignals(False)
        self._debounce.start()

    def _refresh_colors(self) -> None:
        self.strip.set_colors(self._colors, self._shares)
        enabled = bool(self._colors)
        self.new_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.sort_button.setEnabled(len(self._colors) > 1)
        # Shares are gone once a marker was dragged, so "Most Common" means nothing then.
        self.sort_actions["common"].setEnabled(bool(self._shares))
        self.canvas.update()
        self.colorsChanged.emit()

    def sample(self, x: int, y: int) -> str:
        """Color at image pixel (x, y), averaged over the eyedropper sample size."""
        return average_color(pixel_block(self.image.rgb, x, y, self._state.sample_size))

    # ----- zoom -----

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.01, min(zoom, ZOOM_STEPS[-1]))
        if abs(zoom - self._zoom) < 1e-6:
            return
        self._zoom = zoom
        self._update_canvas_size()
        self.zoomChanged.emit(zoom)

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom + 1e-6), ZOOM_STEPS[-1]))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom - 1e-6), ZOOM_STEPS[0]))

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    def fit(self) -> None:
        viewport = self.scroll.viewport().size()
        margin = 24
        scale = min((viewport.width() - margin) / self.image.width, (viewport.height() - margin) / self.image.height)
        self.set_zoom(max(scale, 0.01))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            QTimer.singleShot(0, self.fit)

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport():
            if event.type() == QEvent.Type.Resize:
                self._update_canvas_size()
            elif event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
                return True
        return super().eventFilter(obj, event)

    def _image_size(self) -> QSize:
        return QSize(max(1, round(self.image.width * self._zoom)), max(1, round(self.image.height * self._zoom)))

    def _update_canvas_size(self) -> None:
        viewport = self.scroll.viewport().size()
        size = self._image_size()
        self.canvas.resize(max(size.width(), viewport.width()), max(size.height(), viewport.height()))
        self.canvas.update()

    def image_rect(self) -> QRectF:
        size = self._image_size()
        x = max(0, (self.canvas.width() - size.width()) / 2)
        y = max(0, (self.canvas.height() - size.height()) / 2)
        return QRectF(x, y, size.width(), size.height())

    def marker_point(self, index: int) -> QPointF:
        rect = self.image_rect()
        m = self._markers[index]
        return QPointF(rect.x() + m.x() * rect.width(), rect.y() + m.y() * rect.height())

    def image_pixel_at(self, pos: QPointF, clamp: bool = False) -> tuple[int, int] | None:
        rect = self.image_rect()
        fx = (pos.x() - rect.x()) / rect.width()
        fy = (pos.y() - rect.y()) / rect.height()
        if clamp:
            fx, fy = min(max(fx, 0.0), 0.9999), min(max(fy, 0.0), 0.9999)
        elif not (0 <= fx < 1 and 0 <= fy < 1):
            return None
        return int(fx * self.image.width), int(fy * self.image.height)

    # ----- painting -----

    def displayed_image(self) -> QImage:
        """The image as drawn: simulated while proofing (cached per type/severity)."""
        if not self._state.proof:
            return self._qimage
        key = (self._state.cvd_type, self._state.cvd_severity)
        if key != self._proof_key:
            simulated = LoadedImage(simulate_rgb8(self.image.rgb, *key), self.image.alpha, None, True)
            self._proof_image = to_qimage(simulated)
            self._proof_key = key
        return self._proof_image

    def _update_proof(self, *_args) -> None:
        self.strip.set_color_filter(self._state.proof_filter())
        self.canvas.update()

    def paint_canvas(self, p: QPainter) -> None:
        p.fillRect(p.viewport(), self._theme.color("bg_app"))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._zoom < 1)
        p.drawImage(self.image_rect(), self.displayed_image())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        proof = self._state.proof_filter()
        for i, color in enumerate(self._colors):
            color = proof(color) if proof else color
            center = self.marker_point(i)
            radius = MARKER_RADIUS + (2 if i == self._drag_marker else 0)
            p.setPen(QPen(QColor(0, 0, 0, 150), 1))
            p.setBrush(QColor(color))
            p.drawEllipse(center, radius + 1.5, radius + 1.5)
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.drawEllipse(center, radius, radius)

    # ----- interaction -----

    def _marker_at(self, pos: QPointF) -> int | None:
        for i in reversed(range(len(self._markers))):
            d = self.marker_point(i) - pos
            if math.hypot(d.x(), d.y()) <= MARKER_RADIUS + 3:
                return i
        return None

    def canvas_press(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._state.tool == "eyedropper":
            self._sampling = True
            self._sample_to_background = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            self._sample_foreground(pos, self._sample_to_background)
            return
        self._drag_marker = self._marker_at(pos)
        if self._drag_marker is not None:
            self._move_marker(pos)

    def canvas_move(self, event) -> None:
        pos = event.position()
        if self._sampling:
            self._sample_foreground(pos, self._sample_to_background)
        elif self._drag_marker is not None:
            self._move_marker(pos)
        elif self._state.tool not in ("eyedropper", "hand", "zoom"):
            on_marker = self._marker_at(pos) is not None
            self.canvas.setCursor(Qt.CursorShape.SizeAllCursor if on_marker else Qt.CursorShape.ArrowCursor)

    def canvas_release(self) -> None:
        self._sampling = False
        if self._drag_marker is not None:
            self._drag_marker = None
            self.canvas.update()

    def _sample_foreground(self, pos: QPointF, to_background: bool = False) -> None:
        """Eyedropper: sets the foreground, or the background with Alt (as in Photoshop)."""
        pixel = self.image_pixel_at(pos)
        if pixel is not None:
            (self._state.set_background if to_background else self._state.set_foreground)(self.sample(*pixel))

    def _move_marker(self, pos: QPointF) -> None:
        x, y = self.image_pixel_at(pos, clamp=True)
        i = self._drag_marker
        self._markers[i] = QPointF((x + 0.5) / self.image.width, (y + 0.5) / self.image.height)
        self._colors[i] = self.sample(x, y)
        self._shares = []  # hand-picked colors no longer have a meaningful share
        self._refresh_colors()

    def _update_cursor(self, *_args) -> None:
        cursor = tool_cursor(self._theme, self._state.tool)
        if cursor is None:
            self.canvas.unsetCursor()
        else:
            self.canvas.setCursor(cursor)

    def _on_theme_changed(self, *_args) -> None:
        self._update_cursor()
        self.canvas.update()
