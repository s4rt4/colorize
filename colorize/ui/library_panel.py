"""Libraries panel: saved palettes in the SQLite library, searchable, one strip each."""

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.ui.color_render import paint_swatch

_PALETTE_ROLE = Qt.ItemDataRole.UserRole


class _PaletteDelegate(QStyledItemDelegate):
    """Name above a strip of the palette's colors."""

    ROW_HEIGHT = 50

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        palette = index.data(_PALETTE_ROLE)
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, self._theme.color("bg_selected"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, self._theme.color("bg_hover"))
        painter.setPen(self._theme.color("text"))
        name_rect = QRect(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter, f"{palette.name}")
        painter.setPen(self._theme.color("text_muted"))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{len(palette.colors)}")
        strip = QRect(rect.left() + 8, rect.top() + 24, rect.width() - 16, 18)
        colors = palette.colors or ("#000000",)
        border = self._theme.color("border_input")
        for i, color in enumerate(colors):
            x0 = strip.left() + round(i * strip.width() / len(colors))
            x1 = strip.left() + round((i + 1) * strip.width() / len(colors))
            paint_swatch(painter, QRect(x0, strip.top(), x1 - x0, strip.height()), color, border)


class LibraryPanel(QWidget):
    openRequested = pyqtSignal(object)  # LibraryPalette

    def __init__(self, theme, library, save_action, import_action, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.library = library

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or #hex")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)

        self.list = QListWidget()
        self.list.setItemDelegate(_PaletteDelegate(theme, self.list))
        self.list.setMouseTracking(True)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(lambda item: self.openRequested.emit(item.data(_PALETTE_ROLE)))
        self.list.currentItemChanged.connect(self._sync_buttons)
        self.empty = QLabel("No saved palettes yet.\nUse + to save the active palette.")
        self.empty.setProperty("role", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer = QWidget()
        footer.setObjectName("panelFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(6, 2, 4, 2)
        import_button = QToolButton()
        import_button.setDefaultAction(import_action)
        import_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        row.addWidget(import_button)
        row.addStretch(1)
        save_button = QToolButton()
        save_button.setDefaultAction(save_action)
        save_button.setAutoRaise(True)
        self.delete_button = QToolButton()
        self.delete_button.setToolTip("Delete Palette from Library")
        self.delete_button.setAutoRaise(True)
        theme.bind_icon(self.delete_button, "trash")
        self.delete_button.clicked.connect(self.delete_selected)
        row.addWidget(save_button)
        row.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 0, 8, 0)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(footer)
        theme.changed.connect(self.list.viewport().update)
        self.refresh()

    def selected(self):
        item = self.list.currentItem()
        return item.data(_PALETTE_ROLE) if item is not None else None

    def refresh(self, *_args) -> None:
        current = self.selected()
        self.list.clear()
        palettes = self.library.palettes(self.search.text().strip())
        for palette in palettes:
            item = QListWidgetItem(palette.name)
            item.setData(_PALETTE_ROLE, palette)
            item.setToolTip(f"{palette.name}\n{' '.join(palette.colors)}\nDouble-click to open")
            self.list.addItem(item)
            if current is not None and palette.id == current.id:
                self.list.setCurrentItem(item)
        has_any = bool(palettes) or bool(self.search.text())
        self.list.setVisible(has_any)
        self.empty.setVisible(not has_any)
        self._sync_buttons()

    def select_id(self, palette_id: int) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(_PALETTE_ROLE).id == palette_id:
                self.list.setCurrentRow(i)
                return

    def _sync_buttons(self, *_args) -> None:
        self.delete_button.setEnabled(self.selected() is not None)

    def confirm_delete(self, name: str) -> bool:
        """Separate method so tests can answer it."""
        answer = QMessageBox.question(self, "Delete Palette", f"Delete “{name}” from the library? This cannot be undone.")
        return answer == QMessageBox.StandardButton.Yes

    def delete_selected(self) -> None:
        palette = self.selected()
        if palette is not None and self.confirm_delete(palette.name):
            self.library.delete_palette(palette.id)
            self.refresh()

    def rename_selected(self) -> None:
        palette = self.selected()
        if palette is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Palette", "Name:", text=palette.name)
        if ok and name.strip():
            self.library.rename_palette(palette.id, name.strip())
            self.refresh()

    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.list.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.openRequested.emit(item.data(_PALETTE_ROLE)))
        menu.addAction("Rename…", self.rename_selected)
        menu.addSeparator()
        menu.addAction("Delete…", self.delete_selected)
        menu.exec(self.list.viewport().mapToGlobal(pos))
