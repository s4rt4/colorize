"""Center canvas for one open palette: large swatches, zoom, tool handling."""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QScrollArea

from colorize.ui.navigation import CanvasNavigator, tool_cursor
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
        self._navigator = CanvasNavigator(self, self.grid, state, self.zoom_in, self.zoom_out)
        self.grid.installEventFilter(self)  # installed last, so it runs before the navigator
        state.toolChanged.connect(self._update_cursor)
        theme.changed.connect(self._update_cursor)
        state.proofChanged.connect(self._update_proof)
        state.cvdChanged.connect(self._update_proof)
        self._update_cursor()
        self._update_proof()

    @property
    def title(self) -> str:
        return self.document.palette.name

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

    def _update_proof(self, *_args) -> None:
        self.grid.set_color_filter(self._state.proof_filter())

    def _update_cursor(self, *_args) -> None:
        cursor = tool_cursor(self._theme, self._state.tool)
        if cursor is None:
            self.grid.unsetCursor()
        else:
            self.grid.setCursor(cursor)

    def eventFilter(self, obj, event):
        """Eyedropper on a swatch: make it the foreground color instead of selecting it."""
        if obj is self.grid and self._state.tool == "eyedropper" and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                index = self.grid.index_at(event.position().toPoint())
                if index >= 0:
                    color = self.document.palette.color(index)
                    if event.modifiers() & Qt.KeyboardModifier.AltModifier:  # as in Photoshop
                        self._state.set_background(color)
                    else:
                        self._state.set_foreground(color)
            return True
        return super().eventFilter(obj, event)
