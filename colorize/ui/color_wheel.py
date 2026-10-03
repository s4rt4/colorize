"""Harmony wheel (OKLCH hue x chroma at the base lightness) and the harmony swatch strip."""

import math

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

from colorize.core.color import format_oklch
from colorize.core.gamut import MAX_SRGB_CHROMA
from colorize.core.harmony import offset_of
from colorize.ui.color_render import paint_swatch, wheel_image

HANDLE_RADIUS = 7
BASE_HANDLE_RADIUS = 10
REFINE_DELAY_MS = 200


class HarmonyWheel(QWidget):
    """Drag any handle (or click the disc) to rotate the whole harmony and set its chroma."""

    MARGIN = 12

    def __init__(self, theme, model, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._model = model
        self._cache_key = None
        self._image = None
        self._drag_index: int | None = None
        # While lightness keeps changing (slider drag) render at 1x, then sharpen once it
        # settles; full-resolution renders on 200% screens take longer than a frame.
        self._preview = False
        self._refine = QTimer(self)
        self._refine.setSingleShot(True)
        self._refine.setInterval(REFINE_DELAY_MS)
        self._refine.timeout.connect(self._sharpen)

        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumSize(160, 160)
        self.setCursor(Qt.CursorShape.CrossCursor)
        model.changed.connect(self.update)
        theme.changed.connect(self.update)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return min(width, 340)

    def sizeHint(self) -> QSize:
        return QSize(260, 260)

    # ----- geometry -----

    def _radius(self) -> float:
        return max(10.0, (min(self.width(), self.height()) - 2 * self.MARGIN) / 2)

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def point_for(self, chroma: float, hue: float) -> QPointF:
        r = min(chroma / MAX_SRGB_CHROMA, 1.0) * self._radius()
        angle = math.radians(hue)
        c = self._center()
        return QPointF(c.x() + r * math.cos(angle), c.y() - r * math.sin(angle))

    def polar_at(self, pos: QPointF) -> tuple[float, float]:
        """(chroma, hue) under a widget position; chroma is clamped to the rim."""
        c = self._center()
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        chroma = min(math.hypot(dx, dy) / self._radius(), 1.0) * MAX_SRGB_CHROMA
        return chroma, math.degrees(math.atan2(dy, dx)) % 360

    def handle_at(self, pos: QPointF) -> int | None:
        """Index of the handle under ``pos``; the base wins when handles overlap."""
        harmony = self._model.harmony
        order = [harmony.base_index] + [i for i in range(len(harmony.colors)) if i != harmony.base_index]
        for i in order:
            _, chroma, hue = harmony.colors[i]
            radius = BASE_HANDLE_RADIUS if i == harmony.base_index else HANDLE_RADIUS
            delta = self.point_for(chroma, hue) - pos
            if math.hypot(delta.x(), delta.y()) <= radius + 4:
                return i
        return None

    # ----- painting -----

    def _sharpen(self) -> None:
        self._preview = False
        self.update()

    def _wheel(self):
        side = round(2 * self._radius())
        lightness = round(self._model.base[0], 3)
        if self._cache_key is not None and lightness != self._cache_key[2]:
            self._preview = True
            self._refine.start()
        dpr = self.devicePixelRatioF()
        if self._preview:
            dpr = min(dpr, 1.0)
        bg = self._theme.color("bg_panel")
        key = (side, dpr, lightness, bg.name())
        if key != self._cache_key:
            self._image = wheel_image(side, dpr, lightness, bg)
            self._cache_key = key
        return self._image

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self._theme.color("bg_panel"))
        radius = self._radius()
        c = self._center()
        p.drawImage(QPointF(c.x() - radius, c.y() - radius), self._wheel())

        harmony = self._model.harmony
        points = [self.point_for(ch, h) for _, ch, h in harmony.colors]
        p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
        for point in points:
            p.drawLine(c, point)

        draw_order = [i for i in range(len(points)) if i != harmony.base_index] + [harmony.base_index]
        for i in draw_order:
            mapped = self._model.mapped[i]
            r = BASE_HANDLE_RADIUS if i == harmony.base_index else HANDLE_RADIUS
            p.setBrush(QColor(mapped.hex))
            p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.drawEllipse(points[i], r + 1.5, r + 1.5)
            ring = QPen(QColor("#FFFFFF"), 2)
            if not mapped.in_gamut:
                ring.setStyle(Qt.PenStyle.DashLine)
            p.setPen(ring)
            p.drawEllipse(points[i], r, r)

    # ----- interaction -----

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        self._drag_index = self.handle_at(pos)
        if self._drag_index is None:
            self._drag_index = self._model.harmony.base_index
        self._drag_to(pos)

    def mouseMoveEvent(self, event):
        if self._drag_index is not None:
            self._drag_to(event.position())

    def mouseReleaseEvent(self, _event):
        self._drag_index = None

    def _drag_to(self, pos: QPointF) -> None:
        chroma, hue = self.polar_at(pos)
        base_hue = hue - offset_of(self._model.rule, self._drag_index)
        self._model.edit_base(chroma=chroma, hue=base_hue)


class HarmonySwatches(QWidget):
    """Strip of the harmony's colors. Click one to make it the foreground color.
    The base is underlined; mapped (out-of-gamut) colors carry a warning mark."""

    colorClicked = pyqtSignal(str)
    HEIGHT = 40

    def __init__(self, theme, model, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._model = model
        self.setFixedHeight(self.HEIGHT + 6)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        model.changed.connect(self.update)
        theme.changed.connect(self.update)

    def cell_rect(self, index: int) -> QRect:
        n = len(self._model.mapped)
        width = self.width() / n
        return QRect(round(index * width), 0, round((index + 1) * width) - round(index * width), self.HEIGHT)

    def index_at(self, x: float) -> int:
        n = len(self._model.mapped)
        return max(0, min(int(x / max(self.width(), 1) * n), n - 1))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._theme.color("bg_panel"))
        border = self._theme.color("border_input")
        warning = self._theme.icon("warning")
        for i, mapped in enumerate(self._model.mapped):
            r = self.cell_rect(i)
            paint_swatch(p, r, mapped.hex, border)
            if not mapped.in_gamut:
                badge = QRect(r.right() - 17, r.top() + 3, 14, 14)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setBrush(self._theme.color("bg_panel"))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(badge).adjusted(-1, -1, 1, 1))
                warning.paint(p, badge.adjusted(1, 1, -1, -1))
            if i == self._model.harmony.base_index:
                p.fillRect(QRect(r.left() + 4, r.bottom() + 3, r.width() - 8, 2), self._theme.color("accent"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.colorClicked.emit(self._model.mapped[self.index_at(event.position().x())].hex)

    def event(self, event):
        if event.type() == event.Type.ToolTip:
            i = self.index_at(event.pos().x())
            mapped = self._model.mapped[i]
            lines = [mapped.hex, format_oklch(mapped.hex)]
            if i == self._model.harmony.base_index:
                lines.append("Base color")
            if not mapped.in_gamut:
                lines.append("Outside sRGB: shown with reduced chroma")
            QToolTip.showText(event.globalPos(), "\n".join(lines), self)
            return True
        return super().event(event)
