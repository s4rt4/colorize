"""Context-sensitive options bar under the menu bar, as in Photoshop/Illustrator.

Controls for features of later milestones are present but disabled, so the
layout is settled now.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QWidget,
)

from colorize.ui.tools import TOOLS


def _badge(milestone: str) -> QLabel:
    label = QLabel(milestone)
    label.setProperty("role", "badge")
    label.setToolTip(f"This tool arrives in milestone {milestone}")
    return label


def _row(*items) -> QWidget:
    page = QWidget()
    layout = QHBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for item in items:
        if isinstance(item, str):
            item = QLabel(item)
        layout.addWidget(item)
    layout.addStretch(1)
    return page


def _disabled(widget):
    widget.setEnabled(False)
    return widget


def _combo(*items) -> QComboBox:
    combo = QComboBox()
    combo.addItems(items)
    return combo


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    return label


class OptionsBar(QWidget):
    def __init__(self, theme, state, actions: dict, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._tool = state.tool

        self.tool_icon = QLabel()
        self.tool_icon.setFixedWidth(28)
        self.tool_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}

        def view_buttons():
            buttons = []
            for key, text in (("actual_size", "100%"), ("fit", "Fit Screen")):
                button = QPushButton(text)
                button.clicked.connect(actions[key].trigger)
                buttons.append(button)
            return buttons

        severity = QSlider(Qt.Orientation.Horizontal)
        severity.setRange(0, 100)
        severity.setValue(100)
        severity.setFixedWidth(120)
        count = QSpinBox()
        count.setRange(2, 16)
        count.setValue(5)

        pages = {
            "select": _row(_hint("Click a swatch to select it · drag to reorder · double-click to make it the foreground color")),
            "eyedropper": _row(
                "Sample Size:", _disabled(_combo("Point Sample", "3 by 3 Average", "5 by 5 Average")), _badge("M2")
            ),
            "harmony": _row(
                "Rule:",
                _disabled(
                    _combo("Complementary", "Analogous", "Triadic", "Tetradic", "Split Complementary", "Monochromatic")
                ),
                _badge("M1"),
            ),
            "extract": _row("Colors:", _disabled(count), _badge("M2")),
            "contrast": _row(
                "Algorithm:", _disabled(_combo("WCAG 2.x", "APCA")), "Target:", _disabled(_combo("AA", "AAA")), _badge("M3")
            ),
            "cvd": _row(
                "Type:",
                _disabled(_combo("Protan", "Deutan", "Tritan", "Achromatopsia")),
                "Severity:",
                _disabled(severity),
                _badge("M3"),
            ),
            "hand": _row(*view_buttons()),
            "zoom": _row(*view_buttons(), _hint("Click to zoom in · Alt+click to zoom out")),
        }
        for key, page in pages.items():
            self._pages[key] = page
            self.stack.addWidget(page)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.tool_icon)
        layout.addWidget(self.stack, 1)

        state.toolChanged.connect(self.set_tool)
        theme.changed.connect(self._refresh_icon)
        self.set_tool(state.tool)

    def set_tool(self, key: str) -> None:
        self._tool = key
        self.stack.setCurrentWidget(self._pages[key])
        self._refresh_icon()

    def _refresh_icon(self, *_args) -> None:
        self.tool_icon.setPixmap(self._theme.icon(TOOLS[self._tool].icon).pixmap(18, 18))
        self.tool_icon.setToolTip(TOOLS[self._tool].label)
