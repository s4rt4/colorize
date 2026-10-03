"""Photoshop-style color picker in OKLCH.

Left: chroma x lightness plane at the current hue, then a hue strip. Right: new/current
preview, gamut warning (click to snap into sRGB), and L/C/H/Hex fields.
"""

from PyQt6.QtCore import QLocale, QPointF, QRect, QRegularExpression, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.core.color import hex_to_rgb, normalize_hex, to_oklch
from colorize.core.gamut import MAX_SRGB_CHROMA, map_to_srgb, max_chroma
from colorize.ui.color_render import hue_strip_image, paint_swatch, plane_image


class _Field(QWidget):
    """Base for the plane and hue strip: cached image + drag-to-pick."""

    picked = pyqtSignal(float, float)  # x, y in 0..1

    def __init__(self, theme, size: QSize, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._key = None
        self._image = None
        self.setFixedSize(size)
        self.setCursor(Qt.CursorShape.CrossCursor)
        theme.changed.connect(self.update)

    def _fraction(self, pos: QPointF) -> tuple[float, float]:
        x = min(max(pos.x() / max(self.width() - 1, 1), 0.0), 1.0)
        y = min(max(pos.y() / max(self.height() - 1, 1), 0.0), 1.0)
        return x, y

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(*self._fraction(event.position()))

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.picked.emit(*self._fraction(event.position()))


class ChromaLightnessPlane(_Field):
    def __init__(self, theme, parent=None):
        super().__init__(theme, QSize(256, 256), parent)
        self._lch = (0.5, 0.1, 0.0)

    def set_lch(self, lch) -> None:
        self._lch = lch
        self.update()

    def paintEvent(self, _event):
        lightness, chroma, hue = self._lch
        bg = self._theme.color("bg_panel")
        key = (round(hue, 2), self.devicePixelRatioF(), bg.name())
        if key != self._key:
            self._image = plane_image(self.width(), self.height(), self.devicePixelRatioF(), hue, bg)
            self._key = key
        p = QPainter(self)
        p.drawImage(0, 0, self._image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = min(chroma / MAX_SRGB_CHROMA, 1.0) * (self.width() - 1)
        y = (1.0 - lightness) * (self.height() - 1)
        p.setPen(QPen(QColor("#000000"), 1))
        p.drawEllipse(QPointF(x, y), 6, 6)
        p.setPen(QPen(QColor("#FFFFFF"), 1.5))
        p.drawEllipse(QPointF(x, y), 5, 5)


class HueStrip(_Field):
    def __init__(self, theme, parent=None):
        super().__init__(theme, QSize(22, 256), parent)
        self._hue = 0.0

    def set_hue(self, hue: float) -> None:
        self._hue = hue
        self.update()

    def paintEvent(self, _event):
        dpr = self.devicePixelRatioF()
        if self._key != dpr:
            self._image = hue_strip_image(self.width() - 8, self.height(), dpr)
            self._key = dpr
        p = QPainter(self)
        p.drawImage(4, 0, self._image)
        y = round(self._hue / 360 * (self.height() - 1))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._theme.color("text"))
        for x0, direction in ((0, 1), (self.width(), -1)):
            p.drawPolygon(QPointF(x0, y - 4), QPointF(x0 + 4 * direction, y), QPointF(x0, y + 4))


class _Preview(QWidget):
    """New color on top, current below; clicking 'current' reverts to it."""

    revert = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.new = "#000000"
        self.current = "#000000"
        self.setFixedSize(72, 72)
        self.setToolTip("Top: new color · Bottom: current color (click to restore)")

    def paintEvent(self, _event):
        p = QPainter(self)
        border = self._theme.color("border_input")
        half = self.height() // 2
        paint_swatch(p, QRect(0, 0, self.width(), half + 1), self.new, border)
        paint_swatch(p, QRect(0, half, self.width(), self.height() - half), self.current, border)

    def mousePressEvent(self, event):
        if event.position().y() >= self.height() / 2:
            self.revert.emit()


class ColorPickerDialog(QDialog):
    def __init__(self, theme, initial_hex: str, title: str = "Color Picker", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._theme = theme
        self._initial = normalize_hex(initial_hex)
        self._lch = to_oklch(self._initial)
        self._syncing = False

        self.plane = ChromaLightnessPlane(theme)
        self.plane.picked.connect(lambda x, y: self.set_lch(1.0 - y, x * MAX_SRGB_CHROMA, self._lch[2]))
        self.hue_strip = HueStrip(theme)
        self.hue_strip.picked.connect(lambda _x, y: self.set_lch(self._lch[0], self._lch[1], y * 360))

        self.preview = _Preview(theme)
        self.preview.current = self._initial
        self.preview.revert.connect(lambda: self.set_hex(self._initial))
        self.gamut_button = QToolButton()
        self.gamut_button.setToolTip("Outside sRGB. Click to use the closest color that fits.")
        theme.bind_icon(self.gamut_button, "warning")
        self.gamut_button.clicked.connect(self.fit_to_gamut)

        self.l_field = self._spin(0, 100, 1, " %")
        self.c_field = self._spin(0, 0.4, 3, "")
        self.c_field.setSingleStep(0.005)
        self.h_field = self._spin(0, 360, 1, "°")
        self.h_field.setWrapping(True)
        self.hex_field = QLineEdit()
        self.hex_field.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.hex_field.setMaximumWidth(90)
        self.hex_field.editingFinished.connect(self._hex_edited)
        self.rgb_label = QLabel()
        self.rgb_label.setProperty("role", "muted")
        for field in (self.l_field, self.c_field, self.h_field):
            field.valueChanged.connect(self._fields_edited)

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview)
        preview_row.addWidget(self.gamut_button, 0, Qt.AlignmentFlag.AlignTop)
        preview_row.addStretch(1)
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.addRow("L", self.l_field)
        form.addRow("C", self.c_field)
        form.addRow("H", self.h_field)
        form.addRow("#", self.hex_field)
        form.addRow("RGB", self.rgb_label)
        side = QVBoxLayout()
        side.addLayout(preview_row)
        side.addSpacing(8)
        side.addLayout(form)
        side.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        side.addWidget(buttons)

        body = QHBoxLayout(self)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(10)
        body.addWidget(self.plane)
        body.addWidget(self.hue_strip)
        body.addSpacing(8)
        body.addLayout(side)

        self._sync()

    @staticmethod
    def _spin(low, high, decimals, suffix) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setLocale(QLocale.c())  # decimal point, matching oklch() notation used everywhere else
        spin.setRange(low, high)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        spin.setMinimumWidth(90)
        return spin

    # ----- state -----

    @property
    def lch(self) -> tuple[float, float, float]:
        return self._lch

    def color_hex(self) -> str:
        """The chosen color as sRGB hex (gamut-mapped if the OKLCH value is outside)."""
        return map_to_srgb(*self._lch).hex

    def set_lch(self, lightness: float, chroma: float, hue: float) -> None:
        self._lch = (min(max(lightness, 0.0), 1.0), max(chroma, 0.0), hue % 360)
        self._sync()

    def set_hex(self, hex_color: str) -> None:
        self._lch = to_oklch(hex_color)
        self._sync()

    def fit_to_gamut(self) -> None:
        lightness, _, hue = self._lch
        self.set_lch(lightness, max_chroma(lightness, hue), hue)

    def _fields_edited(self) -> None:
        if not self._syncing:
            self.set_lch(self.l_field.value() / 100, self.c_field.value(), self.h_field.value())

    def _hex_edited(self) -> None:
        try:
            self.set_hex(normalize_hex(self.hex_field.text()))
        except ValueError:
            self._sync()

    def _sync(self) -> None:
        self._syncing = True
        lightness, chroma, hue = self._lch
        mapped = map_to_srgb(lightness, chroma, hue)
        self.l_field.setValue(lightness * 100)
        self.c_field.setValue(chroma)
        self.h_field.setValue(hue)
        self.hex_field.setText(mapped.hex)
        self.rgb_label.setText("{}, {}, {}".format(*hex_to_rgb(mapped.hex)))
        self.gamut_button.setVisible(not mapped.in_gamut)
        self.plane.set_lch(self._lch)
        self.hue_strip.set_hue(hue)
        self.preview.new = mapped.hex
        self.preview.update()
        self._syncing = False


def pick_color(theme, parent, initial: str, title: str) -> str | None:
    """Modal picker; returns ``#RRGGBB`` or None if cancelled."""
    dialog = ColorPickerDialog(theme, initial, title, parent)
    return dialog.color_hex() if dialog.exec() == QDialog.DialogCode.Accepted else None
