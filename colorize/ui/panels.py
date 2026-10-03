"""Dockable panel contents. Docking itself is handled by the main window (ADS)."""

from PyQt6.QtCore import QRegularExpression, Qt
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QUndoView,
    QVBoxLayout,
    QWidget,
)

from colorize.core.color import format_oklch, hex_to_rgb, normalize_hex
from colorize.ui.widgets import ForegroundBackground, SwatchGrid


def _label(text: str = "", role: str | None = None) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    return label


class ColorPanel(QWidget):
    """Foreground/background squares, hex entry and readouts for the foreground color."""

    def __init__(self, theme, state, add_action, sample_action=None, parent=None):
        super().__init__(parent)
        self._state = state

        self.fgbg = ForegroundBackground(theme, state, square=34)
        self.hex_edit = QLineEdit()
        self.hex_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.hex_edit.setMaximumWidth(96)
        self.hex_edit.editingFinished.connect(self._commit_hex)
        self.rgb_label = _label(role="muted")
        self.oklch_label = _label(role="muted")
        self.oklch_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        hex_row = QHBoxLayout()
        hex_row.setSpacing(4)
        hex_row.addWidget(self.hex_edit)
        if sample_action is not None:
            sample_button = QToolButton()
            sample_button.setDefaultAction(sample_action)
            sample_button.setAutoRaise(True)
            hex_row.addWidget(sample_button)
        hex_row.addStretch(1)
        form.addRow("Hex", hex_row)
        form.addRow("RGB", self.rgb_label)
        form.addRow("OKLCH", self.oklch_label)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.fgbg, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(form, 1)

        self._add_action = add_action
        self.add_button = add_button = QPushButton("Add to Swatches")
        add_button.clicked.connect(add_action.trigger)
        add_action.changed.connect(self._sync_add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(add_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        state.colorsChanged.connect(self._refresh)
        self._refresh()

    def _sync_add_button(self) -> None:
        self.add_button.setEnabled(self._add_action.isEnabled())

    def _refresh(self) -> None:
        fg = self._state.foreground
        self.hex_edit.setText(fg)
        r, g, b = hex_to_rgb(fg)
        self.rgb_label.setText(f"{r}, {g}, {b}")
        self.oklch_label.setText(format_oklch(fg))

    def _commit_hex(self) -> None:
        try:
            self._state.set_foreground(normalize_hex(self.hex_edit.text()))
        except ValueError:
            pass
        self._refresh()


class SwatchesPanel(QWidget):
    """Compact view of the active document's palette, with add/delete at the bottom like Adobe."""

    def __init__(self, theme, add_action, delete_action, parent=None):
        super().__init__(parent)
        self.grid = SwatchGrid(theme, chip=22, spacing=3, margin=8, empty_text="No open palette")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid)

        self.count_label = _label(role="muted")
        footer = QWidget()
        footer.setObjectName("panelFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(6, 2, 4, 2)
        row.addWidget(self.count_label, 1)
        for action in (add_action, delete_action):
            button = QToolButton()
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            row.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll, 1)
        layout.addWidget(footer)
        self._update_count()

    def set_document(self, doc) -> None:
        old = self.grid.document
        if old is not None:
            old.palette.changed.disconnect(self._update_count)
        self.grid.set_document(doc)
        if doc is not None:
            doc.palette.changed.connect(self._update_count)
        self._update_count()

    def _update_count(self) -> None:
        doc = self.grid.document
        if doc is None:
            self.count_label.setText("")
            return
        n = len(doc.palette)
        self.count_label.setText(f"{n} swatch" + ("" if n == 1 else "es"))


class HistoryPanel(QUndoView):
    """History of the active document (the QUndoGroup follows the current tab)."""

    def __init__(self, undo_group, parent=None):
        super().__init__(undo_group, parent)
        self.setEmptyLabel("New")


class PlaceholderPanel(QWidget):
    """Stands in for a panel whose feature lands in a later milestone."""

    def __init__(self, theme, icon: str, title: str, milestone: str, description: str, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._icon_name = icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = _label(title, "heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge = _label(f"Coming in {milestone}", "badge")
        text = _label(description, "muted")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addStretch(1)
        layout.addWidget(self.icon_label)
        layout.addWidget(heading)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        layout.addStretch(2)

        theme.changed.connect(self._refresh_icon)
        self._refresh_icon()

    def _refresh_icon(self, *_):
        self.icon_label.setPixmap(self._theme.icon(self._icon_name, muted=True).pixmap(32, 32))
