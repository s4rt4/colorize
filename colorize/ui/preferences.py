"""Edit > Preferences (Ctrl+K). Theme changes preview live; Cancel reverts."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.ui.themes import THEME_LABELS, THEME_ORDER, THEMES


class ThemeSwatchButton(QToolButton):
    """A square showing a theme's panel color, like Adobe's Color Theme picker."""

    def __init__(self, theme_manager, name: str, parent=None):
        super().__init__(parent)
        self._tm = theme_manager
        self.theme_name = name
        self.setCheckable(True)
        self.setFixedSize(QSize(44, 30))
        self.setToolTip(THEME_LABELS[name])

    def paintEvent(self, _event):
        p = QPainter(self)
        rect = self.rect().adjusted(3, 3, -3, -3)
        p.fillRect(rect, QColor(THEMES[self.theme_name]["bg_panel"]))
        if self.isChecked():
            p.setPen(QPen(self._tm.color("accent"), 2))
            p.drawRect(rect.adjusted(-1, -1, 0, 0))
        else:
            p.setPen(self._tm.color("border_input"))
            p.drawRect(rect.adjusted(0, 0, -1, -1))


class PreferencesDialog(QDialog):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._tm = theme_manager
        self._original = theme_manager.name
        self.setWindowTitle("Preferences")
        self.resize(560, 360)

        sections = QListWidget()
        sections.addItem("Interface")
        sections.setCurrentRow(0)
        sections.setFixedWidth(140)

        self.buttons = QButtonGroup(self)
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        for name in THEME_ORDER:
            button = ThemeSwatchButton(theme_manager, name)
            button.setChecked(name == theme_manager.name)
            self.buttons.addButton(button)
            swatch_row.addWidget(button)
        self.theme_label = QLabel(THEME_LABELS[theme_manager.name])
        self.theme_label.setProperty("role", "muted")
        swatch_row.addSpacing(8)
        swatch_row.addWidget(self.theme_label)
        swatch_row.addStretch(1)
        self.buttons.buttonClicked.connect(self._on_theme_clicked)

        hint = QLabel("Shortcuts: Shift+F1 darker · Shift+F2 lighter")
        hint.setProperty("role", "muted")

        appearance = QGroupBox("Appearance")
        group_layout = QVBoxLayout(appearance)
        group_layout.addWidget(QLabel("Color Theme:"))
        group_layout.addLayout(swatch_row)
        group_layout.addWidget(hint)

        interface = QWidget()
        page_layout = QVBoxLayout(interface)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(appearance)
        page_layout.addStretch(1)

        pages = QStackedWidget()
        pages.addWidget(interface)
        sections.currentRowChanged.connect(pages.setCurrentIndex)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(sections)
        body.addWidget(pages, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.addLayout(body, 1)
        layout.addWidget(box, 0, Qt.AlignmentFlag.AlignRight)

        theme_manager.changed.connect(self._sync)

    def _on_theme_clicked(self, button: ThemeSwatchButton) -> None:
        self._tm.apply(button.theme_name)

    def _sync(self, name: str) -> None:
        for button in self.buttons.buttons():
            button.setChecked(button.theme_name == name)
            button.update()
        self.theme_label.setText(THEME_LABELS[name])

    def reject(self) -> None:
        self._tm.apply(self._original)
        super().reject()
