"""Startup splash screen in the style of Adobe apps: artwork, name, version and a
status line that follows startup ("Reading preferences…").

It only imports Qt, so it can be on screen before the heavy modules load.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QConicalGradient, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

# OKLCH hue sweep at L 0.74, chroma following the sRGB edge (same recipe as the logo,
# see tools/make_logo.py), precomputed so the splash needs no color library.
HUE_STOPS = (
    "#FB79A6", "#FB8083", "#FB855A", "#F48E20", "#DA9F20", "#C1AC20", "#9EB921", "#6BC456", "#26C987",
    "#26C5AE", "#25C1C8", "#25BDE2", "#44B5FB", "#7AABFB", "#9BA1FB", "#BA93FB", "#D984ED", "#EF7BCC",
)

WIDTH, HEIGHT = 620, 360
RADIUS = 10


class SplashScreen(QWidget):
    def __init__(self, logo_path: str, version: str):
        super().__init__(
            None,
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)
        self._logo = QIcon(logo_path)
        self._version = version
        self.message = "Starting…"
        self._artwork: QPixmap | None = None  # static part, drawn once; status updates only redraw text
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def show_message(self, text: str) -> None:
        """Update the status line and paint it right away (startup work blocks the event loop)."""
        self.message = text
        self.repaint()
        QApplication.processEvents()

    def finish(self, window: QWidget) -> None:
        window.raise_()
        window.activateWindow()
        self.close()

    # ----- painting -----

    def _ring(self, p: QPainter, center: QPointF, radius: float, width: float, alpha: int) -> None:
        gradient = QConicalGradient(center, 90)
        for i, color in enumerate(HUE_STOPS + HUE_STOPS[:1]):
            c = QColor(color)
            c.setAlpha(alpha)
            gradient.setColorAt(i / len(HUE_STOPS), c)
        pen = QPen(gradient, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        p.drawArc(rect, 40 * 16, 280 * 16)  # a "C": open toward the lower right

    def _paint_artwork(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QPainterPath()
        card.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.setClipPath(card)
        p.fillRect(self.rect(), QColor("#1B1B1B"))

        # Artwork: the logo's hue ring, large and cropped, with a soft glow.
        center = QPointF(WIDTH - 150, HEIGHT / 2 - 10)
        for step in range(12, 0, -1):  # many faint passes read as a soft glow, not bands
            self._ring(p, center, 150, 54 + step * 7, 9)
        self._ring(p, center, 150, 54, 255)
        self._ring(p, center, 76, 6, 70)

        # Fade the artwork into the text side.
        fade = QLinearGradient(260, 0, 430, 0)
        fade.setColorAt(0.0, QColor(27, 27, 27, 255))
        fade.setColorAt(1.0, QColor(27, 27, 27, 0))
        p.fillRect(QRectF(0, 0, 430, HEIGHT), fade)

        self._logo.paint(p, 40, 40, 56, 56)
        title = QFont(self.font())
        title.setPixelSize(40)
        title.setWeight(QFont.Weight.Light)
        p.setFont(title)
        p.setPen(QColor("#F0F0F0"))
        p.drawText(QRectF(40, 116, 300, 50), Qt.AlignmentFlag.AlignVCenter, "Colorize")

        small = QFont(self.font())
        small.setPixelSize(13)
        p.setFont(small)
        p.setPen(QColor("#A8A8A8"))
        p.drawText(QRectF(42, 166, 300, 20), Qt.AlignmentFlag.AlignVCenter, "Offline color manager")
        p.drawText(QRectF(42, 186, 300, 20), Qt.AlignmentFlag.AlignVCenter, f"Version {self._version}")

        tiny = QFont(self.font())
        tiny.setPixelSize(11)
        p.setFont(tiny)
        p.setPen(QColor("#5E5E5E"))
        p.drawText(
            QRectF(42, HEIGHT - 36, 300, 18),
            Qt.AlignmentFlag.AlignVCenter,
            "MIT License · Source Sans 3 under SIL OFL",
        )

        p.setClipping(False)
        p.setPen(QPen(QColor("#3A3A3A"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

    def paintEvent(self, _event):
        dpr = self.devicePixelRatioF()
        if self._artwork is None or self._artwork.devicePixelRatio() != dpr:
            self._artwork = QPixmap(round(WIDTH * dpr), round(HEIGHT * dpr))
            self._artwork.setDevicePixelRatio(dpr)
            self._artwork.fill(Qt.GlobalColor.transparent)
            painter = QPainter(self._artwork)
            self._paint_artwork(painter)
            painter.end()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._artwork)
        tiny = QFont(self.font())
        tiny.setPixelSize(11)
        p.setFont(tiny)
        p.setPen(QColor("#8A8A8A"))
        p.drawText(QRectF(42, HEIGHT - 56, 300, 18), Qt.AlignmentFlag.AlignVCenter, self.message)
