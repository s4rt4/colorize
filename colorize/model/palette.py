"""Palette data and the document that owns it.

The UI never mutates a Palette directly: it calls Document methods, which push
QUndoCommands, so every edit is undoable.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack

from colorize.core.color import normalize_hex
from colorize.model.commands import (
    AddColorCommand,
    MoveColorCommand,
    RemoveColorCommand,
    RenamePaletteCommand,
    SetColorCommand,
)


class Palette(QObject):
    changed = pyqtSignal()
    renamed = pyqtSignal(str)

    def __init__(self, name: str = "Untitled", colors=(), parent=None):
        super().__init__(parent)
        self._name = name
        self._colors = [normalize_hex(c) for c in colors]

    @property
    def name(self) -> str:
        return self._name

    @property
    def colors(self) -> tuple[str, ...]:
        return tuple(self._colors)

    def __len__(self) -> int:
        return len(self._colors)

    def color(self, index: int) -> str:
        return self._colors[index]

    # Mutators below are for commands only.

    def _set_name(self, name: str) -> None:
        self._name = name
        self.renamed.emit(name)

    def _insert(self, index: int, color: str) -> None:
        self._colors.insert(index, normalize_hex(color))
        self.changed.emit()

    def _remove(self, index: int) -> str:
        color = self._colors.pop(index)
        self.changed.emit()
        return color

    def _replace(self, index: int, color: str) -> str:
        old = self._colors[index]
        self._colors[index] = normalize_hex(color)
        self.changed.emit()
        return old

    def _move(self, src: int, dst: int) -> None:
        self._colors.insert(dst, self._colors.pop(src))
        self.changed.emit()


class Document(QObject):
    """One open palette: its data, its undo history and its swatch selection."""

    selectionChanged = pyqtSignal(int)
    modifiedChanged = pyqtSignal(bool)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.palette = palette
        palette.setParent(self)
        self.undo_stack = QUndoStack(self)
        self.path: str | None = None  # file it was opened from / saved to
        self.library_id: int | None = None  # entry in the palette library, if saved there
        self._selected = -1
        # Bound methods, not lambdas: PyQt disconnects them when this object dies, and the
        # stack emits cleanChanged while it is being destroyed.
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        # Connected before any view, so listeners never see a selection past the end.
        palette.changed.connect(self._clamp_selection)

    def _on_clean_changed(self, clean: bool) -> None:
        self.modifiedChanged.emit(not clean)

    def _clamp_selection(self) -> None:
        self.select(self._selected)

    @property
    def selected(self) -> int:
        return self._selected

    @property
    def is_modified(self) -> bool:
        return not self.undo_stack.isClean()

    def select(self, index: int) -> None:
        index = max(-1, min(index, len(self.palette) - 1))
        if index != self._selected:
            self._selected = index
            self.selectionChanged.emit(index)

    def add_color(self, color: str, index: int | None = None) -> None:
        if index is None:
            index = len(self.palette)
        self.undo_stack.push(AddColorCommand(self, normalize_hex(color), index))

    def add_colors(self, colors, text: str = "Add Swatches") -> None:
        """Append several colors as one undo step."""
        colors = [normalize_hex(c) for c in colors]
        if not colors:
            return
        self.undo_stack.beginMacro(text)
        for color in colors:
            self.undo_stack.push(AddColorCommand(self, color, len(self.palette)))
        self.undo_stack.endMacro()

    def remove_color(self, index: int) -> None:
        self.undo_stack.push(RemoveColorCommand(self, index))

    def set_color(self, index: int, color: str) -> None:
        color = normalize_hex(color)
        if self.palette.color(index) != color:
            self.undo_stack.push(SetColorCommand(self, index, color))

    def move_color(self, src: int, dst: int) -> None:
        if src != dst:
            self.undo_stack.push(MoveColorCommand(self, src, dst))

    def rename(self, name: str) -> None:
        name = name.strip()
        if name and name != self.palette.name:
            self.undo_stack.push(RenamePaletteCommand(self, name))
