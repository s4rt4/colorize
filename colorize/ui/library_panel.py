"""Libraries panel: saved palettes in the SQLite library, searchable, filterable by tag,
or ranked by how close their colors are to the foreground color."""

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QComboBox,
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
_DISTANCE_ROLE = Qt.ItemDataRole.UserRole + 1


class _PaletteDelegate(QStyledItemDelegate):
    """Name (and tags) above a strip of the palette's colors."""

    ROW_HEIGHT = 50

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        palette = index.data(_PALETTE_ROLE)
        distance = index.data(_DISTANCE_ROLE)
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, self._theme.color("bg_selected"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, self._theme.color("bg_hover"))
        line = QRect(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18)
        right = f"ΔE {distance * 100:.1f}" if distance is not None else f"{len(palette.colors)}"
        right_width = painter.fontMetrics().horizontalAdvance(right) + 8
        painter.setPen(self._theme.color("text_muted"))
        painter.drawText(line, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, right)
        text_area = line.adjusted(0, 0, -right_width, 0)
        metrics = painter.fontMetrics()
        name = metrics.elidedText(palette.name, Qt.TextElideMode.ElideRight, text_area.width())
        painter.setPen(self._theme.color("text"))
        painter.drawText(text_area, Qt.AlignmentFlag.AlignVCenter, name)
        if palette.tags:
            used = metrics.horizontalAdvance(name) + 8
            tags = metrics.elidedText(
                " · ".join(palette.tags), Qt.TextElideMode.ElideRight, max(0, text_area.width() - used)
            )
            painter.setPen(self._theme.color("text_muted"))
            painter.drawText(text_area.adjusted(used, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, tags)
        strip = QRect(rect.left() + 8, rect.top() + 24, rect.width() - 16, 18)
        colors = palette.colors or ("#000000",)
        border = self._theme.color("border_input")
        for i, color in enumerate(colors):
            x0 = strip.left() + round(i * strip.width() / len(colors))
            x1 = strip.left() + round((i + 1) * strip.width() / len(colors))
            paint_swatch(painter, QRect(x0, strip.top(), x1 - x0, strip.height()), color, border)


class LibraryPanel(QWidget):
    openRequested = pyqtSignal(object)  # LibraryPalette

    def __init__(self, theme, library, save_action, import_action, state=None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state
        self.library = library

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name, tag or #hex")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)

        self.tag_filter = QComboBox()
        self.tag_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tag_filter.setMinimumContentsLength(6)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.similar = QToolButton()
        self.similar.setCheckable(True)
        self.similar.setText("Similar")
        self.similar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.similar.setToolTip("Show palettes with a color close to the foreground color, closest first")
        theme.bind_icon(self.similar, "target")
        self.similar.toggled.connect(self.refresh)
        if state is not None:
            state.colorsChanged.connect(self._on_colors_changed)
        else:
            self.similar.setEnabled(False)

        self.list = QListWidget()
        self.list.setItemDelegate(_PaletteDelegate(theme, self.list))
        self.list.setMouseTracking(True)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(lambda item: self.openRequested.emit(item.data(_PALETTE_ROLE)))
        self.list.currentItemChanged.connect(self._sync_buttons)
        self.empty = QLabel()
        self.empty.setProperty("role", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)

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
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(8, 0, 8, 0)
        filter_row.addWidget(self.tag_filter, 1)
        filter_row.addWidget(self.similar)
        layout.addLayout(search_row)
        layout.addLayout(filter_row)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(footer)
        theme.changed.connect(self.list.viewport().update)
        self.refresh()

    def selected(self):
        item = self.list.currentItem()
        return item.data(_PALETTE_ROLE) if item is not None else None

    def _rebuild_tags(self) -> None:
        current = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", None)
        for tag, count in self.library.all_tags():
            self.tag_filter.addItem(f"{tag} ({count})", tag)
        index = self.tag_filter.findData(current) if current else 0
        self.tag_filter.setCurrentIndex(max(index, 0))
        self.tag_filter.blockSignals(False)

    def _on_colors_changed(self) -> None:
        if self.similar.isChecked():
            self.refresh()

    def refresh(self, *_args) -> None:
        self._rebuild_tags()
        current = self.selected()
        search = self.search.text().strip()
        tag = self.tag_filter.currentData()
        self.list.clear()
        if self.similar.isChecked() and self._state is not None:
            allowed = {p.id for p in self.library.palettes(search, tag)} if (search or tag) else None
            rows = [
                (match.palette, match.distance)
                for match in self.library.similar_palettes(self._state.foreground)
                if allowed is None or match.palette.id in allowed
            ]
            empty_text = f"No saved palette has a color close to {self._state.foreground}."
        else:
            rows = [(palette, None) for palette in self.library.palettes(search, tag)]
            empty_text = (
                "No palettes match." if (search or tag) else "No saved palettes yet.\nUse + to save the active palette."
            )
        for palette, distance in rows:
            item = QListWidgetItem(palette.name)
            item.setData(_PALETTE_ROLE, palette)
            item.setData(_DISTANCE_ROLE, distance)
            tags = f"\nTags: {', '.join(palette.tags)}" if palette.tags else ""
            item.setToolTip(f"{palette.name}{tags}\n{' '.join(palette.colors)}\nDouble-click to open")
            self.list.addItem(item)
            if current is not None and palette.id == current.id:
                self.list.setCurrentItem(item)
        self.empty.setText(empty_text)
        self.list.setVisible(bool(rows))
        self.empty.setVisible(not rows)
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

    def edit_tags_selected(self) -> None:
        palette = self.selected()
        if palette is None:
            return
        text, ok = QInputDialog.getText(
            self, "Edit Tags", "Tags, separated by commas:", text=", ".join(palette.tags)
        )
        if ok:
            self.library.set_tags(palette.id, text.split(","))
            self.refresh()

    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.list.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.openRequested.emit(item.data(_PALETTE_ROLE)))
        menu.addAction("Rename…", self.rename_selected)
        menu.addAction("Edit Tags…", self.edit_tags_selected)
        menu.addSeparator()
        menu.addAction("Delete…", self.delete_selected)
        menu.exec(self.list.viewport().mapToGlobal(pos))
