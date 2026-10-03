"""Undoable palette edits. Each command also restores the swatch selection."""

import weakref

from PyQt6.QtGui import QUndoCommand

SET_COLOR_ID = 1


class _DocumentCommand(QUndoCommand):
    """Holds the document weakly: the document's undo stack owns its commands, and a
    strong back-reference forms a cycle that crashes PyQt at interpreter shutdown."""

    def __init__(self, text: str, doc):
        super().__init__(text)
        self._doc_ref = weakref.ref(doc)

    @property
    def doc(self):
        return self._doc_ref()


class AddColorCommand(_DocumentCommand):
    def __init__(self, doc, color: str, index: int):
        super().__init__("Add Swatch", doc)
        self.color, self.index = color, index
        self.prev_selected = doc.selected

    def redo(self):
        self.doc.palette._insert(self.index, self.color)
        self.doc.select(self.index)

    def undo(self):
        self.doc.palette._remove(self.index)
        self.doc.select(self.prev_selected)


class RemoveColorCommand(_DocumentCommand):
    def __init__(self, doc, index: int):
        super().__init__("Delete Swatch", doc)
        self.index = index
        self.color = doc.palette.color(index)

    def redo(self):
        self.doc.palette._remove(self.index)
        self.doc.select(min(self.index, len(self.doc.palette) - 1))

    def undo(self):
        self.doc.palette._insert(self.index, self.color)
        self.doc.select(self.index)


class SetColorCommand(_DocumentCommand):
    """Consecutive edits of the same swatch merge into one history step."""

    def __init__(self, doc, index: int, color: str):
        super().__init__("Edit Swatch", doc)
        self.index, self.new = index, color
        self.old = doc.palette.color(index)

    def id(self):
        return SET_COLOR_ID

    def mergeWith(self, other):
        if other.id() != self.id() or other.index != self.index:
            return False
        self.new = other.new
        return True

    def redo(self):
        self.doc.palette._replace(self.index, self.new)
        self.doc.select(self.index)

    def undo(self):
        self.doc.palette._replace(self.index, self.old)
        self.doc.select(self.index)


class MoveColorCommand(_DocumentCommand):
    def __init__(self, doc, src: int, dst: int):
        super().__init__("Move Swatch", doc)
        self.src, self.dst = src, dst

    def redo(self):
        self.doc.palette._move(self.src, self.dst)
        self.doc.select(self.dst)

    def undo(self):
        self.doc.palette._move(self.dst, self.src)
        self.doc.select(self.src)


class RenamePaletteCommand(_DocumentCommand):
    def __init__(self, doc, name: str):
        super().__init__("Rename Palette", doc)
        self.new = name
        self.old = doc.palette.name

    def redo(self):
        self.doc.palette._set_name(self.new)

    def undo(self):
        self.doc.palette._set_name(self.old)
