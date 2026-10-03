"""Gradient panel: foreground -> background, mixed in OKLab (or OKLCH / sRGB)."""

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from colorize.core.mix import INTERPOLATION_LABELS, INTERPOLATIONS, css_linear_gradient, gradient
from colorize.ui.widgets import ColorStrip, ForegroundBackground

BAR_SAMPLES = 48  # QLinearGradient interpolates in sRGB between stops; this many keeps that invisible


class GradientBar(QWidget):
    """Continuous preview, drawn from colors computed in the chosen space."""

    def __init__(self, theme, height: int = 30, label: str = "", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._colors: list[str] = []
        self._label = label
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        theme.changed.connect(self.update)

    def set_colors(self, colors) -> None:
        self._colors = list(colors)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = QLinearGradient(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        for i, color in enumerate(self._colors):
            fill.setColorAt(i / max(len(self._colors) - 1, 1), QColor(color))
        p.fillRect(rect, fill)
        p.setPen(self._theme.color("border_input"))
        p.drawRect(rect)
        if self._label:
            font = QFont(self.font())
            font.setPixelSize(10)
            p.setFont(font)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(rect.adjusted(6, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self._label)


class GradientPanel(QWidget):
    addRequested = pyqtSignal(list)
    newPaletteRequested = pyqtSignal(str, list)

    def __init__(self, theme, state, parent=None):
        super().__init__(parent)
        self._state = state

        self.pair = ForegroundBackground(theme, state, square=24)
        pair_hint = QLabel("From foreground to background\nX swaps the ends")
        pair_hint.setProperty("role", "muted")
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self.pair)
        top.addWidget(pair_hint, 1)

        self.space = QComboBox()
        for space in INTERPOLATIONS:
            self.space.addItem(INTERPOLATION_LABELS[space], space)
        self.space.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.space.setMinimumContentsLength(8)
        self.count = QSpinBox()
        self.count.setRange(2, 21)
        self.count.setValue(7)
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.addRow("Mix in", self.space)
        form.addRow("Steps", self.count)

        self.bar = GradientBar(theme, 30)
        self.compare = GradientBar(theme, 14, "sRGB")
        self.compare.setToolTip("The same two colors mixed in sRGB, for comparison")
        self.steps = ColorStrip(theme, 30)
        self.steps.setToolTip("Click a step to copy its hex")
        self.steps.colorClicked.connect(self._copy_hex)

        self.css = QLabel()
        self.css.setProperty("role", "muted")
        self.css.setWordWrap(True)
        self.css.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.add_button = QPushButton("Add to Swatches")
        self.add_button.clicked.connect(lambda: self.addRequested.emit(self.colors()))
        self.new_button = QPushButton("New Palette")
        self.new_button.clicked.connect(
            lambda: self.newPaletteRequested.emit(f"Gradient {self._state.foreground}–{self._state.background}", self.colors())
        )
        self.copy_button = QPushButton("Copy CSS")
        self.copy_button.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.css_text()))
        buttons = QHBoxLayout()
        for button in (self.add_button, self.new_button, self.copy_button):
            buttons.addWidget(button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(form)
        layout.addWidget(self.bar)
        layout.addWidget(self.compare)
        layout.addWidget(self.steps)
        layout.addWidget(self.css)
        layout.addLayout(buttons)
        layout.addStretch(1)

        state.colorsChanged.connect(self.refresh)
        self.space.currentIndexChanged.connect(self.refresh)
        self.count.valueChanged.connect(self.refresh)
        self.refresh()

    def stops(self) -> list[str]:
        return [self._state.foreground, self._state.background]

    def colors(self) -> list[str]:
        return gradient(self.stops(), self.count.value(), self.space.currentData())

    def css_text(self) -> str:
        return css_linear_gradient(self.stops(), self.space.currentData())

    def _copy_hex(self, hex_color: str) -> None:
        QGuiApplication.clipboard().setText(hex_color)

    def refresh(self, *_args) -> None:
        space = self.space.currentData()
        self.bar.set_colors(gradient(self.stops(), BAR_SAMPLES, space))
        self.compare.set_colors(gradient(self.stops(), BAR_SAMPLES, "srgb"))
        self.compare.setVisible(space != "srgb")
        self.steps.set_colors(self.colors())
        self.css.setText(self.css_text())
