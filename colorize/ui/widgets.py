"""Custom-painted widgets shared by panels and documents."""

import math

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QColorDialog, QSizePolicy, QWidget


def paint_swatch(p: QPainter, rect: QRect, color, border) -> None:
    """Bordered color square built from two fills, so the edge stays exact at
    fractional display scaling (a 1px drawRect can leave a sliver of fill outside it)."""
    p.fillRect(rect, QColor(border))
    p.fillRect(rect.adjusted(1, 1, -1, -1), QColor(color))


def pick_color(parent, initial: str, title: str) -> str | None:
    """Non-native dialog so it follows the app theme. Returns ``#RRGGBB`` or None."""
    color = QColorDialog.getColor(
        QColor(initial), parent, title, QColorDialog.ColorDialogOption.DontUseNativeDialog
    )
    return color.name().upper() if color.isValid() else None


class ColorChip(QWidget):
    """A plain bordered square of one color."""

    def __init__(self, theme, size: int = 12, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._color = QColor("#000000")
        self.setFixedSize(size, size)
        theme.changed.connect(self.update)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event):
        paint_swatch(QPainter(self), self.rect(), self._color, self._theme.color("text_muted"))


class SwatchGrid(QWidget):
    """Flowing grid of a document's swatches: click selects, drag reorders,
    double-click emits ``activated``. Edits go through Document (undoable)."""

    activated = pyqtSignal(int)
    contextMenuRequested = pyqtSignal(int, QPoint)

    def __init__(
        self,
        theme,
        chip: int = 24,
        spacing: int = 4,
        margin: int = 8,
        show_labels: bool = False,
        background: str = "bg_panel",
        empty_text: str = "No swatches",
        parent=None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._doc = None
        self._chip = chip
        self._spacing = spacing
        self._margin = margin
        self._show_labels = show_labels
        self._background = background
        self._empty_text = empty_text
        self._press_index = -1
        self._press_pos = QPoint()
        self._drop_index: int | None = None

        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._label_font = QFont(self.font())
        self._label_font.setPixelSize(11)
        theme.changed.connect(self.update)

    # ----- document binding -----

    @property
    def document(self):
        return self._doc

    def set_document(self, doc) -> None:
        if doc is self._doc:
            return
        if self._doc is not None:
            self._doc.palette.changed.disconnect(self._on_palette_changed)
            self._doc.selectionChanged.disconnect(self._on_selection_changed)
        self._doc = doc
        if doc is not None:
            doc.palette.changed.connect(self._on_palette_changed)
            doc.selectionChanged.connect(self._on_selection_changed)
        self._on_palette_changed()

    def _on_palette_changed(self):
        self.updateGeometry()
        self.update()

    def _on_selection_changed(self, _index):
        self.update()

    # ----- geometry -----

    @property
    def chip_size(self) -> int:
        return self._chip

    def set_chip_size(self, px: int) -> None:
        px = max(8, px)
        if px != self._chip:
            self._chip = px
            self.updateGeometry()
            self.update()

    def _count(self) -> int:
        return len(self._doc.palette) if self._doc is not None else 0

    def _label_height(self, chip: int) -> int:
        return self.fontMetrics().height() + 4 if self._show_labels and chip >= 40 else 0

    def _columns(self, width: int, chip: int) -> int:
        return max(1, (width - 2 * self._margin + self._spacing) // (chip + self._spacing))

    def height_for(self, width: int, chip: int) -> int:
        n = max(self._count(), 1)
        rows = math.ceil(n / self._columns(width, chip))
        cell_h = chip + self._label_height(chip)
        return 2 * self._margin + rows * cell_h + (rows - 1) * self._spacing

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self.height_for(width, self._chip)

    def sizeHint(self) -> QSize:
        width = 2 * self._margin + 6 * (self._chip + self._spacing)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        side = 2 * self._margin + self._chip
        return QSize(side, side)

    def cell_rect(self, index: int) -> QRect:
        cols = self._columns(self.width(), self._chip)
        row, col = divmod(index, cols)
        cell_h = self._chip + self._label_height(self._chip)
        x = self._margin + col * (self._chip + self._spacing)
        y = self._margin + row * (cell_h + self._spacing)
        return QRect(x, y, self._chip, self._chip)

    def index_at(self, pos: QPoint) -> int:
        for i in range(self._count()):
            if self.cell_rect(i).contains(pos):
                return i
        return -1

    def _drop_index_at(self, pos: QPoint) -> int:
        n = self._count()
        cols = self._columns(self.width(), self._chip)
        cell_h = self._chip + self._label_height(self._chip)
        step_x = self._chip + self._spacing
        col = max(0, min(round((pos.x() - self._margin) / step_x), cols))
        rows = max(1, math.ceil(n / cols))
        row = max(0, min((pos.y() - self._margin) // (cell_h + self._spacing), rows - 1))
        return max(0, min(row * cols + col, n))

    # ----- painting -----

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._theme.color(self._background))
        n = self._count()
        if n == 0:
            p.setPen(self._theme.color("text_muted"))
            p.drawText(
                self.rect().adjusted(12, 12, -12, -12),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._empty_text,
            )
            return

        border = self._theme.color("border_input")
        muted = self._theme.color("text_muted")
        accent = self._theme.color("accent")
        label_h = self._label_height(self._chip)
        p.setFont(self._label_font)
        for i, hex_color in enumerate(self._doc.palette.colors):
            r = self.cell_rect(i)
            paint_swatch(p, r, hex_color, border)
            if label_h:
                p.setPen(muted)
                text_rect = QRect(r.left() - 8, r.bottom() + 3, r.width() + 16, label_h)
                p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, hex_color)
            if i == self._doc.selected:
                p.setPen(QPen(accent, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r.adjusted(-2, -2, 1, 1))

        if self._drop_index is not None:
            if self._drop_index < n:
                r = self.cell_rect(self._drop_index)
                x = r.left() - self._spacing // 2 - 1
            else:
                r = self.cell_rect(n - 1)
                x = r.right() + self._spacing // 2 + 1
            p.setPen(QPen(accent, 2))
            p.drawLine(x, r.top() - 2, x, r.bottom() + 2)

    # ----- interaction -----

    def mousePressEvent(self, event):
        if self._doc is None or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.position().toPoint()
        self._press_index = self.index_at(pos)
        self._press_pos = pos
        self._doc.select(self._press_index)
        self.setFocus()

    def mouseMoveEvent(self, event):
        if self._press_index < 0 or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self._drop_index is None and (pos - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._drop_index = self._drop_index_at(pos)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drop_index is not None and self._press_index >= 0:
            target = self._drop_index
            dst = target - 1 if target > self._press_index else target
            self._doc.move_color(self._press_index, dst)
        self._press_index = -1
        self._drop_index = None
        self.update()

    def mouseDoubleClickEvent(self, event):
        index = self.index_at(event.position().toPoint())
        if index >= 0:
            self.activated.emit(index)

    def contextMenuEvent(self, event):
        index = self.index_at(event.pos())
        if self._doc is not None and index >= 0:
            self._doc.select(index)
            self.contextMenuRequested.emit(index, event.globalPos())

    def keyPressEvent(self, event):
        if self._doc is None or self._count() == 0:
            return super().keyPressEvent(event)
        cols = self._columns(self.width(), self._chip)
        step = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: -cols,
            Qt.Key.Key_Down: cols,
        }.get(event.key())
        if step is None:
            return super().keyPressEvent(event)
        current = max(self._doc.selected, 0)
        self._doc.select(max(0, min(current + step, self._count() - 1)))


class ForegroundBackground(QWidget):
    """Photoshop-style overlapping foreground/background squares.

    Click a square to pick its color, the arrow to swap (X), the mini squares to reset (D).
    """

    def __init__(self, theme, state, square: int = 22, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state
        self._sq = square
        offset = square * 6 // 10
        side = square + offset + 2
        self.setFixedSize(side, side)
        self._fg = QRect(1, 1, square, square)
        self._bg = QRect(1 + offset, 1 + offset, square, square)
        mini = max(10, square // 2)
        self._swap = QRect(side - mini, 0, mini, mini)
        self._default = QRect(0, side - mini, mini, mini)
        self.setToolTip("Foreground / Background color\nClick to pick · X swap · D default")
        state.colorsChanged.connect(self.update)
        theme.changed.connect(self.update)

    def paintEvent(self, _event):
        p = QPainter(self)
        frame = self._theme.color("text_muted")
        outline = self._theme.color("bg_panel")
        for rect, color in ((self._bg, self._state.background), (self._fg, self._state.foreground)):
            paint_swatch(p, rect, outline, frame)  # frame plus a panel-colored inner ring
            p.fillRect(rect.adjusted(2, 2, -2, -2), QColor(color))
        self._theme.icon("swap", muted=True).paint(p, self._swap)
        d = self._default
        small = d.width() * 6 // 10
        paint_swatch(p, QRect(d.right() - small + 1, d.bottom() - small + 1, small, small), "#FFFFFF", frame)
        paint_swatch(p, QRect(d.left(), d.top() + 1, small, small), "#000000", frame)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if self._swap.contains(pos):
            self._state.swap_colors()
        elif self._default.contains(pos):
            self._state.reset_colors()
        elif self._fg.contains(pos):
            color = pick_color(self, self._state.foreground, "Foreground Color")
            if color:
                self._state.set_foreground(color)
        elif self._bg.contains(pos):
            color = pick_color(self, self._state.background, "Background Color")
            if color:
                self._state.set_background(color)
