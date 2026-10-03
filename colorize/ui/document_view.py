"""Center canvas for one open palette: large swatches, zoom, Hand/Zoom tool handling."""

from PyQt6.QtCore import QEvent, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QScrollArea

from colorize.ui.widgets import SwatchGrid

BASE_CHIP = 64
ZOOM_STEPS = (0.25, 0.33, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0)


class DocumentView(QScrollArea):
    zoomChanged = pyqtSignal(float)

    def __init__(self, document, state, theme, parent=None):
        super().__init__(parent)
        self.document = document
        self._state = state
        self._theme = theme
        self._zoom = 1.0
        self._tool = state.tool
        self._pan_origin: QPoint | None = None
        self._pan_start = (0, 0)

        self.setObjectName("canvas")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.grid = SwatchGrid(
            theme,
            chip=BASE_CHIP,
            spacing=16,
            margin=32,
            show_labels=True,
            background="bg_app",
            empty_text="Empty palette.\nAdd the foreground color with the + button in the Swatches panel.",
        )
        self.grid.set_document(document)
        self.setWidget(self.grid)
        self.grid.installEventFilter(self)
        state.toolChanged.connect(self._on_tool_changed)
        theme.changed.connect(self._update_cursor)
        self._update_cursor()

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        zoom = max(ZOOM_STEPS[0] / 2, min(zoom, ZOOM_STEPS[-1]))
        if abs(zoom - self._zoom) < 1e-6:
            return
        self._zoom = zoom
        self.grid.set_chip_size(round(BASE_CHIP * zoom))
        self.zoomChanged.emit(zoom)

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom + 1e-6), ZOOM_STEPS[-1]))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom - 1e-6), ZOOM_STEPS[0]))

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    def fit(self) -> None:
        """Largest chip size at which every swatch is visible without scrolling."""
        viewport = self.viewport().size()
        chip = 12
        for candidate in range(256, 11, -2):
            if self.grid.height_for(viewport.width(), candidate) <= viewport.height():
                chip = candidate
                break
        self.set_zoom(chip / BASE_CHIP)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    # ----- Hand and Zoom tools act on the canvas instead of the swatches -----

    def _on_tool_changed(self, tool: str) -> None:
        self._tool = tool
        self._pan_origin = None
        self._update_cursor()

    def _update_cursor(self, *_args) -> None:
        if self._tool == "hand":
            self.grid.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._tool == "zoom":
            pixmap = self._theme.icon("zoom").pixmap(20, 20)
            self.grid.setCursor(QCursor(pixmap, 8, 8))
        else:
            self.grid.unsetCursor()

    def eventFilter(self, obj, event):
        if obj is not self.grid or self._tool not in ("hand", "zoom"):
            return super().eventFilter(obj, event)
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self._tool == "hand":
                self._pan_origin = event.globalPosition().toPoint()
                self._pan_start = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
                self.grid.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.zoom_out()
            else:
                self.zoom_in()
            return True
        if kind == QEvent.Type.MouseMove and self._pan_origin is not None:
            delta = event.globalPosition().toPoint() - self._pan_origin
            self.horizontalScrollBar().setValue(self._pan_start[0] - delta.x())
            self.verticalScrollBar().setValue(self._pan_start[1] - delta.y())
            return True
        if kind == QEvent.Type.MouseButtonRelease:
            self._pan_origin = None
            self._update_cursor()
            return True
        if kind in (QEvent.Type.MouseButtonDblClick, QEvent.Type.ContextMenu, QEvent.Type.MouseMove):
            return True
        return super().eventFilter(obj, event)
