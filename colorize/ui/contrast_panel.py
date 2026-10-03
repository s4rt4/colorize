"""Contrast panel: foreground as text on background, WCAG 2.x + APCA, fixes that pass."""

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.core.contrast import (
    APCA_TARGETS,
    METHODS,
    WCAG_NON_TEXT,
    WCAG_TARGETS,
    apca_contrast,
    apca_guidance,
    contrast_ratio,
    format_ratio,
    passes,
    suggest_text_colors,
)
from colorize.ui.color_render import paint_swatch
from colorize.ui.widgets import ForegroundBackground

METHOD_LABELS = {"wcag": "WCAG 2.x", "apca": "APCA (guidance)"}


def method_combo(state) -> QComboBox:
    combo = QComboBox()
    for method in METHODS:
        combo.addItem(METHOD_LABELS[method], method)
    combo.setCurrentIndex(METHODS.index(state.contrast_method))
    combo.currentIndexChanged.connect(lambda i: state.set_contrast(METHODS[i]))
    state.contrastChanged.connect(lambda: combo.setCurrentIndex(METHODS.index(state.contrast_method)))
    return combo


def target_combo(state) -> QComboBox:
    """Target list follows the method (WCAG levels or APCA Lc levels)."""
    combo = QComboBox()

    def rebuild():
        targets = WCAG_TARGETS if state.contrast_method == "wcag" else APCA_TARGETS
        combo.blockSignals(True)
        combo.clear()
        for key, (label, value) in targets.items():
            text = f"{label} ({value:g}:1)" if state.contrast_method == "wcag" else label
            combo.addItem(text, key)
        combo.setCurrentIndex(list(targets).index(state.contrast_target))
        combo.blockSignals(False)

    combo.currentIndexChanged.connect(lambda i: state.set_contrast(state.contrast_method, combo.itemData(i)))
    state.contrastChanged.connect(rebuild)
    rebuild()
    return combo


class ContrastPreview(QWidget):
    """Sample text in the foreground color on the background color."""

    def __init__(self, theme, state, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        state.colorsChanged.connect(self.update)
        theme.changed.connect(self.update)

    def paintEvent(self, _event):
        p = QPainter(self)
        paint_swatch(p, self.rect(), self._state.background, self._theme.color("border_input"))
        p.setPen(QColor(self._state.foreground))
        big = QFont(self.font())
        big.setPixelSize(30)
        big.setWeight(QFont.Weight.DemiBold)
        p.setFont(big)
        p.drawText(QRect(12, 6, 70, 46), Qt.AlignmentFlag.AlignVCenter, "Aa")
        small = QFont(self.font())
        small.setPixelSize(13)
        p.setFont(small)
        p.drawText(
            QRect(80, 10, self.width() - 90, self.height() - 20),
            Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            "The quick brown fox jumps over the lazy dog. 0123456789",
        )


class SuggestionButton(QToolButton):
    """A color chip + hex that makes that color the foreground when clicked."""

    chosen = pyqtSignal(str)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.hex = "#000000"
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumHeight(28)
        self.clicked.connect(lambda: self.chosen.emit(self.hex))

    def set_suggestion(self, hex_color: str, text: str) -> None:
        self.hex = hex_color
        self.setText("        " + text)  # room for the painted chip
        self.setToolTip(f"Use {hex_color} as the text (foreground) color")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        paint_swatch(p, QRect(6, (self.height() - 16) // 2, 16, 16), self.hex, self._theme.color("border_input"))


def _set_status(label: QLabel, text: str, ok: bool) -> None:
    label.setText(("✓ " if ok else "✕ ") + text)
    label.setProperty("role", "pass" if ok else "fail")
    label.style().unpolish(label)
    label.style().polish(label)


class ContrastPanel(QWidget):
    def __init__(self, theme, state, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state

        self.pair = ForegroundBackground(theme, state, square=28)
        pair_hint = QLabel("Text = foreground\nBackground = background\nX swaps them")
        pair_hint.setProperty("role", "muted")
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.pair, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(pair_hint, 1)

        self.preview = ContrastPreview(theme, state)

        # WCAG: ratio on the left, pass/fail per level on the right.
        self.ratio = QLabel()
        self.ratio.setProperty("role", "metric")
        wcag_title = QLabel("WCAG 2.x")
        wcag_title.setProperty("role", "heading")
        wcag_left = QVBoxLayout()
        wcag_left.setSpacing(0)
        wcag_left.addWidget(wcag_title)
        wcag_left.addWidget(self.ratio)
        self.wcag_grid = QGridLayout()
        self.wcag_grid.setHorizontalSpacing(12)
        self.wcag_grid.setVerticalSpacing(1)
        self.wcag_labels = [QLabel() for _ in range(len(WCAG_TARGETS) + 1)]
        for i, label in enumerate(self.wcag_labels):
            self.wcag_grid.addWidget(label, i // 2, i % 2)
        wcag_row = QHBoxLayout()
        wcag_row.setSpacing(14)
        wcag_row.addLayout(wcag_left)
        wcag_row.addLayout(self.wcag_grid, 1)

        # APCA: Lc value and what it is good for.
        self.lc = QLabel()
        self.lc.setProperty("role", "metric")
        apca_title = QLabel("APCA")
        apca_title.setProperty("role", "heading")
        apca_title.setToolTip("Draft WCAG 3 method: guidance only, not a conformance requirement")
        apca_left = QVBoxLayout()
        apca_left.setSpacing(0)
        apca_left.addWidget(apca_title)
        apca_left.addWidget(self.lc)
        self.apca_note = QLabel()
        self.apca_note.setWordWrap(True)
        badge = QLabel("guidance")
        badge.setProperty("role", "badge")
        badge.setToolTip(apca_title.toolTip())
        apca_right = QVBoxLayout()
        apca_right.setSpacing(4)
        apca_right.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        apca_right.addWidget(self.apca_note)
        apca_row = QHBoxLayout()
        apca_row.setSpacing(14)
        apca_row.addLayout(apca_left)
        apca_row.addLayout(apca_right, 1)

        self.method = method_combo(state)
        self.target = target_combo(state)
        for combo in (self.method, self.target):  # let the row shrink in a narrow dock
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(5)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Fix for"))
        target_row.addWidget(self.method)
        target_row.addWidget(self.target, 1)
        self.fix_status = QLabel()
        self.fix_status.setWordWrap(True)
        self.suggestions = [SuggestionButton(theme) for _ in range(2)]
        for button in self.suggestions:
            button.chosen.connect(state.set_foreground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.preview)
        layout.addLayout(wcag_row)
        layout.addLayout(apca_row)
        layout.addLayout(target_row)
        layout.addWidget(self.fix_status)
        for button in self.suggestions:
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        state.colorsChanged.connect(self._refresh)
        state.contrastChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        text, background = self._state.foreground, self._state.background
        ratio = contrast_ratio(text, background)
        self.ratio.setText(format_ratio(ratio))

        checks = [(label, ratio >= value) for label, value in WCAG_TARGETS.values()]
        checks.append((f"UI {WCAG_NON_TEXT:g}:1", ratio >= WCAG_NON_TEXT))
        for widget, (label, ok) in zip(self.wcag_labels, checks):
            _set_status(widget, label, ok)

        lc = apca_contrast(text, background)
        self.lc.setText(f"Lc {lc:.1f}")
        self.apca_note.setText(apca_guidance(lc))

        method, target = self._state.contrast_method, self._state.contrast_target
        label = (WCAG_TARGETS if method == "wcag" else APCA_TARGETS)[target][0]
        for button in self.suggestions:
            button.hide()
        if passes(method, target, text, background):
            self.fix_status.setText(f"✓ Passes {label}")
            self.fix_status.setProperty("role", "pass")
        else:
            found = suggest_text_colors(method, target, text, background)
            if found:
                self.fix_status.setText(f"Closest text colors that pass {label}:")
                self.fix_status.setProperty("role", "muted")
                for button, suggestion in zip(self.suggestions, found):
                    change = abs(suggestion.lightness_change) * 100
                    button.set_suggestion(suggestion.hex, f"{suggestion.hex}  ·  {change:.0f}% {suggestion.direction}")
                    button.show()
            else:
                self.fix_status.setText(f"No text color passes {label} on this background; change the background.")
                self.fix_status.setProperty("role", "fail")
        self.fix_status.style().unpolish(self.fix_status)
        self.fix_status.style().polish(self.fix_status)
