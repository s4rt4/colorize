"""Match panel: nearest colors from a color book (CSS names or a user-imported book
such as Pantone or RAL) for the foreground and for every swatch, by CIEDE2000."""

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from colorize.core.books import CSS_BOOK_ID, BookColor, ColorBook, css_named_book
from colorize.formats import import_named_colors
from colorize.formats.swatch_files import SwatchFileError
from colorize.ui.print_panel import split_chip

FOREGROUND_MATCHES = 5
_HEX_ROLE = Qt.ItemDataRole.UserRole


def _tree(headers) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setRootIsDecorated(False)
    tree.setHeaderLabels(headers)
    tree.setIconSize(QSize(36, 18))
    tree.setUniformRowHeights(True)
    header = tree.header()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # names get the room, ΔE stays narrow
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    return tree


class MatchPanel(QWidget):
    def __init__(self, theme, state, library, settings, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state
        self._library = library
        self._settings = settings
        self._doc = None
        self._books: dict[int, ColorBook] = {}
        self._dirty = True
        self.palette_matches = []

        self.book = QComboBox()
        self.book.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.book.setMinimumContentsLength(10)
        self.book.currentIndexChanged.connect(self._book_changed)
        import_button = QToolButton()
        import_button.setToolTip("Import a color book (.ase or .gpl, e.g. exported Pantone or RAL swatches)")
        theme.bind_icon(import_button, "plus")
        import_button.clicked.connect(lambda: self.import_book())
        self.delete_button = QToolButton()
        self.delete_button.setToolTip("Remove this color book")
        theme.bind_icon(self.delete_button, "trash")
        self.delete_button.clicked.connect(self.delete_book)
        book_row = QHBoxLayout()
        book_row.addWidget(QLabel("Book"))
        book_row.addWidget(self.book, 1)
        book_row.addWidget(import_button)
        book_row.addWidget(self.delete_button)

        self.foreground_title = QLabel()
        self.foreground_title.setProperty("role", "heading")
        self.foreground = _tree(["Closest", "ΔE"])
        self.foreground.setToolTip("Double-click to make it the foreground color")
        self.foreground.itemDoubleClicked.connect(lambda item: state.set_foreground(item.data(0, _HEX_ROLE)))

        palette_title = QLabel("Palette")
        palette_title.setProperty("role", "heading")
        self.palette = _tree(["Swatch → match", "ΔE"])
        self.use_button = QPushButton("Use Book Colors")
        self.use_button.setToolTip("Replace every swatch with its closest book color (one undo step)")
        self.use_button.clicked.connect(self.use_book_colors)
        note = QLabel("Proprietary books (Pantone, RAL) aren't bundled: import your own .ase or .gpl.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addLayout(book_row)
        layout.addWidget(self.foreground_title)
        layout.addWidget(self.foreground, 1)
        layout.addWidget(palette_title)
        layout.addWidget(self.palette, 2)
        buttons = QHBoxLayout()
        buttons.addWidget(self.use_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(note)

        self._fill_books(settings.value("match/book", CSS_BOOK_ID, type=int))
        state.colorsChanged.connect(self.refresh)
        theme.changed.connect(self.refresh)

    # ----- books -----

    def _fill_books(self, select_id: int) -> None:
        self.book.blockSignals(True)
        self.book.clear()
        self.book.addItem("CSS Named Colors (148)", CSS_BOOK_ID)
        for book_id, name, count in self._library.books():
            self.book.addItem(f"{name} ({count})", book_id)
        index = self.book.findData(select_id)
        self.book.setCurrentIndex(index if index >= 0 else 0)
        self.book.blockSignals(False)
        self._book_changed()

    def current_book(self) -> ColorBook:
        book_id = self.book.currentData()
        if book_id not in self._books:
            if book_id == CSS_BOOK_ID:
                self._books[book_id] = css_named_book()
            else:
                name = self.book.currentText().rsplit(" (", 1)[0]
                colors = [BookColor(n, h) for n, h in self._library.book_colors(book_id)]
                self._books[book_id] = ColorBook(book_id, name, colors)
        return self._books[book_id]

    def _book_changed(self, *_args) -> None:
        self.delete_button.setEnabled(self.book.currentData() != CSS_BOOK_ID)
        self._settings.setValue("match/book", self.book.currentData())
        self.refresh()

    def import_book(self, path: str | None = None) -> int | None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import Color Book", "", "Swatches (*.ase *.gpl)")
            if not path:
                return None
        try:
            name, entries = import_named_colors(path)
        except (OSError, SwatchFileError) as exc:
            QMessageBox.warning(self, "Import Color Book", f"Could not read “{Path(path).name}”:\n{exc}")
            return None
        if not entries:
            QMessageBox.warning(self, "Import Color Book", f"“{Path(path).name}” has no colors.")
            return None
        book_id = self._library.add_book(name, entries, source=str(path))
        self._fill_books(book_id)
        return book_id

    def confirm_delete(self, name: str) -> bool:
        """Separate method so tests can answer it."""
        answer = QMessageBox.question(self, "Remove Color Book", f"Remove “{name}” from Colorize?")
        return answer == QMessageBox.StandardButton.Yes

    def delete_book(self) -> None:
        book_id = self.book.currentData()
        if book_id == CSS_BOOK_ID or not self.confirm_delete(self.book.currentText()):
            return
        self._library.delete_book(book_id)
        self._books.pop(book_id, None)
        self._fill_books(CSS_BOOK_ID)

    # ----- matching -----

    def set_document(self, doc) -> None:
        if self._doc is not None:
            self._doc.palette.changed.disconnect(self.refresh)
        self._doc = doc
        if doc is not None:
            doc.palette.changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self.refresh()

    def refresh(self, *_args) -> None:
        if not self.isVisible():
            self._dirty = True  # big books cost real time; match when shown
            return
        self._dirty = False
        book = self.current_book()
        border = self._theme.color("border_input")

        foreground = self._state.foreground
        self.foreground_title.setText(f"Closest to the foreground ({foreground})")
        self.foreground.clear()
        for match in book.nearest(foreground, FOREGROUND_MATCHES):
            item = QTreeWidgetItem([f"{match.color.name}  {match.color.hex}", f"{match.delta_e:.1f}"])
            item.setIcon(0, split_chip(foreground, match.color.hex, border))
            item.setData(0, _HEX_ROLE, match.color.hex)
            self.foreground.addTopLevelItem(item)

        colors = list(self._doc.palette.colors) if self._doc is not None else []
        self.palette_matches = [book.nearest(c, 1)[0] for c in colors] if book.colors else []
        self.palette.clear()
        for hex_color, match in zip(colors, self.palette_matches):
            item = QTreeWidgetItem([f"{hex_color} → {match.color.name}", f"{match.delta_e:.1f}"])
            item.setIcon(0, split_chip(hex_color, match.color.hex, border))
            item.setToolTip(0, f"{hex_color} → {match.color.name} ({match.color.hex})")
            self.palette.addTopLevelItem(item)
        self.use_button.setEnabled(any(m.color.hex != c for c, m in zip(colors, self.palette_matches)))

    def use_book_colors(self) -> None:
        if self._doc is None or not self.palette_matches:
            return
        stack = self._doc.undo_stack
        stack.beginMacro(f"Use {self.current_book().name}")
        for index, match in enumerate(self.palette_matches):
            self._doc.set_color(index, match.color.hex)
        stack.endMacro()
