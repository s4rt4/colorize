"""Sample a color from anywhere on screen.

Every screen is captured at its own device resolution and covered by a frozen,
full-screen overlay with a magnifier. A click maps the logical cursor position to
that screen's device pixels (pos x devicePixelRatio), so monitors with different
scaling each sample the pixel actually under the cursor.

Captured values are display values, treated as sRGB (no monitor profile is applied).
"""

import math

import numpy as np
from PyQt6.QtCore import QObject, QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from colorize.core.extract import average_color
from colorize.core.image import pixel_block

LOUPE_PIXELS = 11  # device pixels shown across the magnifier
LOUPE_SIZE = 132  # logical size of the magnifier


def image_to_rgb(image: QImage) -> np.ndarray:
    """QImage -> (H, W, 3) uint8 copy."""
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    w, h, stride = image.width(), image.height(), image.bytesPerLine()
    data = np.frombuffer(image.constBits().asstring(stride * h), dtype=np.uint8)
    return data.reshape(h, stride)[:, : w * 3].reshape(h, w, 3).copy()


def device_pixel(pos: QPointF, dpr: float, width: int, height: int) -> tuple[int, int]:
    """Logical position on a screen -> device pixel of that screen's capture."""
    x = int(math.floor(pos.x() * dpr))
    y = int(math.floor(pos.y() * dpr))
    return min(max(x, 0), width - 1), min(max(y, 0), height - 1)


class ScreenOverlay(QWidget):
    def __init__(self, sampler, screen, capture, sample_size: int):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._sampler = sampler
        self._capture = capture  # QPixmap in device pixels, with this screen's DPR
        self._dpr = capture.devicePixelRatio()
        self._image = capture.toImage()  # converted once; the loupe reads from it on every move
        self._rgb = image_to_rgb(self._image)
        self._sample_size = sample_size
        self._cursor = QPointF(-1000, -1000)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        if screen is not None:
            self.setScreen(screen)
            self.setGeometry(screen.geometry())

    def color_at(self, pos: QPointF) -> str:
        h, w = self._rgb.shape[:2]
        x, y = device_pixel(pos, self._dpr, w, h)
        return average_color(pixel_block(self._rgb, x, y, self._sample_size))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._capture)
        if self._cursor.x() < 0:
            return
        h, w = self._rgb.shape[:2]
        cx, cy = device_pixel(self._cursor, self._dpr, w, h)
        half = LOUPE_PIXELS // 2
        source = QRect(cx - half, cy - half, LOUPE_PIXELS, LOUPE_PIXELS)
        offset = QPointF(24, 24)
        loupe = QRectF(self._cursor + offset, self._cursor + offset + QPointF(LOUPE_SIZE, LOUPE_SIZE))
        if loupe.right() > self.width():
            loupe.moveRight(self._cursor.x() - offset.x())
        if loupe.bottom() > self.height() - 30:
            loupe.moveBottom(self._cursor.y() - offset.y())
        p.fillRect(loupe, QColor("#000000"))
        p.drawImage(loupe, self._image, QRectF(source))
        cell = loupe.width() / LOUPE_PIXELS
        size = self._sample_size
        p.setPen(QPen(QColor("#FFFFFF"), 1.5))
        p.drawRect(QRectF(loupe.x() + (half - size // 2) * cell, loupe.y() + (half - size // 2) * cell, cell * size, cell * size))
        p.setPen(QPen(QColor("#000000"), 1))
        p.drawRect(loupe)
        color = self.color_at(self._cursor)
        label = QRectF(loupe.x(), loupe.bottom() + 4, loupe.width(), 22)
        p.fillRect(label, QColor(30, 30, 30, 230))
        p.fillRect(QRectF(label.x() + 5, label.y() + 5, 12, 12), QColor(color))
        p.setPen(QColor("#FFFFFF"))
        font = QFont(self.font())
        font.setPixelSize(12)
        p.setFont(font)
        p.drawText(label.adjusted(24, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, f"{color}   Esc to cancel")

    def mouseMoveEvent(self, event):
        self._cursor = event.position()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._sampler.finish(self.color_at(event.position()))
        else:
            self._sampler.cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._sampler.cancel()


class ScreenSampler(QObject):
    picked = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, grab=None, parent=None):
        super().__init__(parent)
        self._grab = grab or (lambda screen: screen.grabWindow(0))
        self.overlays: list[ScreenOverlay] = []

    @property
    def active(self) -> bool:
        return bool(self.overlays)

    def start(self, sample_size: int = 1) -> None:
        if self.active:
            return
        for screen in QGuiApplication.screens():
            capture = self._grab(screen)
            if capture.isNull():
                continue
            overlay = ScreenOverlay(self, screen, capture, sample_size)
            self.overlays.append(overlay)
            overlay.show()
        if self.overlays:
            self.overlays[0].activateWindow()
            self.overlays[0].setFocus()
        else:
            self.finished.emit()

    def finish(self, color: str) -> None:
        self._close()
        self.picked.emit(color)

    def cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        overlays, self.overlays = self.overlays, []
        for overlay in overlays:
            overlay.close()
        self.finished.emit()
