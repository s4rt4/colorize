"""Harmony panel: rule, OKLCH wheel, lightness/chroma sliders, result strip."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.core.gamut import MAX_SRGB_CHROMA
from colorize.core.harmony import RULE_LABELS, RULES
from colorize.ui.color_wheel import HarmonySwatches, HarmonyWheel

CHROMA_SCALE = 1000  # slider units per chroma unit


def rule_combo(model) -> QComboBox:
    """Rule picker kept in sync with the model (used here and in the options bar)."""
    combo = QComboBox()
    for rule in RULES:
        combo.addItem(RULE_LABELS[rule], rule)
    combo.setCurrentIndex(RULES.index(model.rule))
    combo.currentIndexChanged.connect(lambda i: model.set_rule(RULES[i]))
    model.ruleChanged.connect(lambda rule: combo.setCurrentIndex(RULES.index(rule)))
    return combo


class HarmonyPanel(QWidget):
    def __init__(self, theme, model, state, add_action, parent=None):
        super().__init__(parent)
        self._model = model
        self._state = state

        self.rule = rule_combo(model)
        use_fg = QToolButton()
        use_fg.setToolTip("Use Foreground Color as Base")
        theme.bind_icon(use_fg, "target")
        use_fg.clicked.connect(lambda: model.set_base_hex(state.foreground))
        top = QHBoxLayout()
        top.addWidget(QLabel("Rule"))
        top.addWidget(self.rule, 1)
        top.addWidget(use_fg)

        self.wheel = HarmonyWheel(theme, model)

        self.lightness = QSlider(Qt.Orientation.Horizontal)
        self.lightness.setRange(0, 1000)
        self.lightness.valueChanged.connect(lambda v: model.edit_base(lightness=v / 1000))
        self.chroma = QSlider(Qt.Orientation.Horizontal)
        self.chroma.setRange(0, round(MAX_SRGB_CHROMA * CHROMA_SCALE))
        self.chroma.valueChanged.connect(lambda v: model.edit_base(chroma=v / CHROMA_SCALE))
        self.lightness_value = QLabel()
        self.chroma_value = QLabel()
        for label in (self.lightness_value, self.chroma_value):
            label.setProperty("role", "muted")
            label.setMinimumWidth(44)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sliders = QGridLayout()
        sliders.setHorizontalSpacing(8)
        sliders.addWidget(QLabel("Lightness"), 0, 0)
        sliders.addWidget(self.lightness, 0, 1)
        sliders.addWidget(self.lightness_value, 0, 2)
        sliders.addWidget(QLabel("Chroma"), 1, 0)
        sliders.addWidget(self.chroma, 1, 1)
        sliders.addWidget(self.chroma_value, 1, 2)

        self.swatches = HarmonySwatches(theme, model)
        self.swatches.colorClicked.connect(state.set_foreground)

        self.gamut_note = QLabel()
        self.gamut_note.setProperty("role", "muted")
        self.gamut_note.setWordWrap(True)

        self.add_button = QPushButton("Add to Swatches")
        self.add_button.setToolTip("Add every harmony color to the open palette (one undo step)")
        self._add_action = add_action
        self.add_button.clicked.connect(add_action.trigger)
        add_action.changed.connect(self._sync_add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self.wheel, 1)
        layout.addLayout(sliders)
        layout.addWidget(self.swatches)
        layout.addWidget(self.gamut_note)
        layout.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

        model.changed.connect(self._refresh)
        self._refresh()
        self._sync_add_button()

    def _sync_add_button(self) -> None:
        self.add_button.setEnabled(self._add_action.isEnabled())

    def _refresh(self) -> None:
        lightness, chroma, _ = self._model.base
        for slider, value in ((self.lightness, round(lightness * 1000)), (self.chroma, round(chroma * CHROMA_SCALE))):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.lightness_value.setText(f"{lightness * 100:.0f}%")
        self.chroma_value.setText(f"{chroma:.3f}")
        outside = sum(not m.in_gamut for m in self._model.mapped)
        self.gamut_note.setVisible(outside > 0)
        if outside:
            self.gamut_note.setText(
                f"{outside} of {len(self._model.mapped)} colors are outside sRGB and shown with reduced chroma."
            )
