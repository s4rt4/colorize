"""Sample a color from anywhere on screen.

Every screen is captured at its own device resolution and covered by a frozen,
full-screen overlay with a magnifier. A click maps the logical cursor position to
that screen's device pixels (pos x devicePixelRatio), so monitors with different
scaling each sample the pixel actually under the cursor.

Captured values are display values, treated as sRGB (no monitor profile is applied).

On Wayland an app may not read the screen, so the picture comes from
xdg-desktop-portal's Screenshot request instead (one image of the whole desktop,
cut into screens). The overlay and loupe work the same way after that.
"""

import itertools
import math
import os
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

if sys.platform.startswith("linux"):  # the portal lives on the session bus; not bundled elsewhere
    from PyQt6.QtDBus import QDBusConnection, QDBusMessage
else:
    QDBusConnection = QDBusMessage = None

from colorize.core.extract import average_color
from colorize.core.image import pixel_block

LOUPE_PIXELS = 11  # device pixels shown across the magnifier
LOUPE_SIZE = 132  # logical size of the magnifier

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
_tokens = itertools.count(1)


def needs_portal(platform: str = sys.platform, env=os.environ) -> bool:
    """Wayland sessions hide other windows from screen grabs (also under XWayland)."""
    return platform.startswith("linux") and (env.get("XDG_SESSION_TYPE") == "wayland" or bool(env.get("WAYLAND_DISPLAY")))


def portal_request_path(unique_name: str, token: str) -> str:
    """The Request object path the portal will use (lets us subscribe before calling)."""
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


def split_desktop(image: QImage, screens) -> list[tuple[object, QPixmap]]:
    """Cut one whole-desktop picture into each screen's part.

    The portal image spans the union of the screens' logical geometries at one scale
    (image width / union width), which becomes each part's device pixel ratio.
    """
    union = QRect()
    for screen in screens:
        union = union.united(screen.geometry())
    if image.isNull() or union.isEmpty():
        return []
    sx, sy = image.width() / union.width(), image.height() / union.height()
    parts = []
    for screen in screens:
        g = screen.geometry()
        rect = QRect(round((g.x() - union.x()) * sx), round((g.y() - union.y()) * sy),
                     round(g.width() * sx), round(g.height() * sy))
        pixmap = QPixmap.fromImage(image.copy(rect))
        pixmap.setDevicePixelRatio(sx)
        parts.append((screen, pixmap))
    return parts


class PortalScreenshot(QObject):
    """One org.freedesktop.portal.Screenshot request; ``done`` carries the local file
    path of the picture, or "" when cancelled, denied or unavailable."""

    done = pyqtSignal(str)

    def request(self) -> None:
        if QDBusConnection is None:
            self.done.emit("")
            return
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            self.done.emit("")
            return
        token = f"colorize{os.getpid()}_{next(_tokens)}"
        self._path = portal_request_path(bus.baseService(), token)
        bus.connect(PORTAL_SERVICE, self._path, "org.freedesktop.portal.Request", "Response", self._on_response)
        call = QDBusMessage.createMethodCall(PORTAL_SERVICE, PORTAL_PATH, "org.freedesktop.portal.Screenshot", "Screenshot")
        call.setArguments(["", {"handle_token": token, "interactive": False}])
        reply = bus.call(call)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            bus.disconnect(PORTAL_SERVICE, self._path, "org.freedesktop.portal.Request", "Response", self._on_response)
            self.done.emit("")

    @(pyqtSlot(QDBusMessage) if QDBusMessage is not None else (lambda f: f))
    def _on_response(self, message) -> None:
        QDBusConnection.sessionBus().disconnect(PORTAL_SERVICE, self._path, "org.freedesktop.portal.Request", "Response",
                                                self._on_response)
        code, results = (list(message.arguments()) + [1, {}])[:2]  # (response, a{sv} results)
        uri = results.get("uri", "") if code == 0 and isinstance(results, dict) else ""
        self.done.emit(QUrl(str(uri)).toLocalFile() if uri else "")


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

    def __init__(self, grab=None, parent=None, portal=None):
        """``grab(screen) -> QPixmap`` captures directly; ``portal() -> PortalScreenshot``
        is used instead when the session needs it (Wayland) or when given (tests)."""
        super().__init__(parent)
        self._grab = grab or (lambda screen: screen.grabWindow(0))
        self._portal_factory = portal or (PortalScreenshot if grab is None and needs_portal() else None)
        self._portal = None
        self.overlays: list[ScreenOverlay] = []

    @property
    def active(self) -> bool:
        return bool(self.overlays) or self._portal is not None

    def start(self, sample_size: int = 1) -> None:
        if self.active:
            return
        if self._portal_factory is not None:
            self._portal = self._portal_factory()
            self._portal.done.connect(lambda path: self._portal_done(path, sample_size))
            self._portal.request()
            return
        self._show([(screen, self._grab(screen)) for screen in QGuiApplication.screens()], sample_size, False)

    def _portal_done(self, path: str, sample_size: int) -> None:
        self._portal = None
        image = QImage(path) if path else QImage()
        if path:
            Path(path).unlink(missing_ok=True)  # the portal saved it only for this request
        self._show(split_desktop(image, QGuiApplication.screens()), sample_size, True)

    def _show(self, captures, sample_size: int, fullscreen: bool) -> None:
        for screen, capture in captures:
            if capture.isNull():
                continue
            overlay = ScreenOverlay(self, screen, capture, sample_size)
            self.overlays.append(overlay)
            # Wayland ignores window positions: ask for full screen on that output instead
            overlay.showFullScreen() if fullscreen else overlay.show()
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
