"""Scale panel: a 50-950 tint/shade scale from one base color."""

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from colorize.core.color import format_oklch
from colorize.core.scale import DARKEST, LIGHTEST, tint_shade_scale
from colorize.ui.color_render import paint_swatch
from colorize.ui.widgets import ColorChip


class ScaleStrip(QWidget):
    """Eleven swatches with their step numbers; the base step is underlined."""

    colorClicked = pyqtSignal(str)
    SWATCH_HEIGHT = 34
    LABEL_HEIGHT = 18

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.steps = []
        self.setFixedHeight(self.SWATCH_HEIGHT + self.LABEL_HEIGHT + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._font = QFont(self.font())
        self._font.setPixelSize(10)
        theme.changed.connect(self.update)

    def set_steps(self, steps) -> None:
        self.steps = list(steps)
        self.update()

    def cell_rect(self, index: int) -> QRect:
        n = max(len(self.steps), 1)
        x0 = round(index * self.width() / n)
        x1 = round((index + 1) * self.width() / n)
        return QRect(x0, 0, x1 - x0, self.SWATCH_HEIGHT)

    def index_at(self, x: float) -> int:
        if not self.steps:
            return -1
        return max(0, min(int(x / max(self.width(), 1) * len(self.steps)), len(self.steps) - 1))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._theme.color("bg_panel"))
        border = self._theme.color("border_input")
        p.setFont(self._font)
        for i, step in enumerate(self.steps):
            r = self.cell_rect(i)
            paint_swatch(p, r, step.hex, border)
            label = QRect(r.left(), r.bottom() + 3, r.width(), self.LABEL_HEIGHT)
            p.setPen(self._theme.color("text" if step.is_base else "text_muted"))
            p.drawText(label, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, str(step.step))
            if step.is_base:
                p.fillRect(QRect(r.left() + 3, self.height() - 2, r.width() - 6, 2), self._theme.color("accent"))

    def mousePressEvent(self, event):
        index = self.index_at(event.position().x())
        if event.button() == Qt.MouseButton.LeftButton and index >= 0:
            self.colorClicked.emit(self.steps[index].hex)

    def event(self, event):
        if event.type() == event.Type.ToolTip:
            index = self.index_at(event.pos().x())
            if index >= 0:
                step = self.steps[index]
                text = f"{step.step}  ·  {step.hex}\n{format_oklch(step.hex)}"
                if step.is_base:
                    text += "\nBase color"
                QToolTip.showText(event.globalPos(), text, self)
            return True
        return super().event(event)


class ScalePanel(QWidget):
    addRequested = pyqtSignal(list)
    newPaletteRequested = pyqtSignal(str, list)

    def __init__(self, theme, state, base: str = "#3D6A9E", parent=None):
        super().__init__(parent)
        self._state = state
        self.base = base

        self.base_chip = ColorChip(theme, 26)
        self.base_label = QLabel()
        use_fg = QToolButton()
        use_fg.setToolTip("Use Foreground Color as Base")
        theme.bind_icon(use_fg, "target")
        use_fg.clicked.connect(lambda: self.set_base(state.foreground))
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.base_chip)
        top.addWidget(self.base_label, 1)
        top.addWidget(use_fg)

        self.strip = ScaleStrip(theme)
        self.strip.colorClicked.connect(state.set_foreground)

        self.lightest = QSlider(Qt.Orientation.Horizontal)
        self.lightest.setRange(85, 99)
        self.lightest.setValue(round(LIGHTEST * 100))
        self.darkest = QSlider(Qt.Orientation.Horizontal)
        self.darkest.setRange(10, 45)
        self.darkest.setValue(round(DARKEST * 100))
        self.lightest_value = QLabel()
        self.darkest_value = QLabel()
        sliders = QGridLayout()
        sliders.setHorizontalSpacing(8)
        for row, (label, slider, value) in enumerate(
            (("Lightest (50)", self.lightest, self.lightest_value), ("Darkest (950)", self.darkest, self.darkest_value))
        ):
            value.setProperty("role", "muted")
            value.setMinimumWidth(34)
            sliders.addWidget(QLabel(label), row, 0)
            sliders.addWidget(slider, row, 1)
            sliders.addWidget(value, row, 2)
            slider.valueChanged.connect(self.refresh)

        hint = QLabel("Even OKLCH lightness steps; the base keeps its exact value.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)

        self.add_button = QPushButton("Add to Swatches")
        self.add_button.clicked.connect(lambda: self.addRequested.emit(self.colors()))
        self.new_button = QPushButton("New Palette")
        self.new_button.clicked.connect(lambda: self.newPaletteRequested.emit(f"Scale {self.base}", self.colors()))
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.new_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.strip)
        layout.addLayout(sliders)
        layout.addWidget(hint)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.refresh()

    def set_base(self, hex_color: str) -> None:
        self.base = hex_color
        self.refresh()

    def colors(self) -> list[str]:
        return [step.hex for step in self.strip.steps]

    def refresh(self, *_args) -> None:
        lightest, darkest = self.lightest.value() / 100, self.darkest.value() / 100
        self.lightest_value.setText(f"{self.lightest.value()}%")
        self.darkest_value.setText(f"{self.darkest.value()}%")
        steps = tint_shade_scale(self.base, lightest, darkest)
        self.strip.set_steps(steps)
        self.base_chip.set_color(self.base)
        base_step = next(s.step for s in steps if s.is_base)
        self.base_label.setText(f"{self.base}  ·  lands on {base_step}")
