"""Hand and Zoom tool behavior shared by every canvas (palette and image views)."""

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtGui import QCursor

NAVIGATION_TOOLS = ("hand", "zoom")


def tool_cursor(theme, tool: str) -> QCursor | None:
    """Cursor for a tool, or None for the widget's own cursor."""
    if tool == "hand":
        return QCursor(Qt.CursorShape.OpenHandCursor)
    if tool == "zoom":
        return QCursor(theme.icon("zoom").pixmap(20, 20), 8, 8)
    if tool == "eyedropper":
        return QCursor(theme.icon("eyedropper").pixmap(20, 20), 4, 16)  # hotspot at the tip
    return None


class CanvasNavigator(QObject):
    """Event filter on a canvas inside a QScrollArea: drag to pan with Hand,
    click to zoom in (Alt+click out) with Zoom. Other tools pass through."""

    def __init__(self, scroll_area, canvas, state, zoom_in, zoom_out):
        super().__init__(scroll_area)
        self._scroll = scroll_area
        self._canvas = canvas
        self._state = state
        self._zoom_in = zoom_in
        self._zoom_out = zoom_out
        self._pan_origin: QPoint | None = None
        self._pan_start = (0, 0)
        canvas.installEventFilter(self)

    def eventFilter(self, obj, event):
        tool = self._state.tool
        if obj is not self._canvas or tool not in NAVIGATION_TOOLS:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if tool == "hand":
                self._pan_origin = event.globalPosition().toPoint()
                self._pan_start = (self._scroll.horizontalScrollBar().value(), self._scroll.verticalScrollBar().value())
                self._canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._zoom_out()
            else:
                self._zoom_in()
            return True
        if kind == QEvent.Type.MouseMove and self._pan_origin is not None:
            delta = event.globalPosition().toPoint() - self._pan_origin
            self._scroll.horizontalScrollBar().setValue(self._pan_start[0] - delta.x())
            self._scroll.verticalScrollBar().setValue(self._pan_start[1] - delta.y())
            return True
        if kind == QEvent.Type.MouseButtonRelease:
            if self._pan_origin is not None:
                self._pan_origin = None
                self._canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            return True
        return kind in (QEvent.Type.MouseButtonDblClick, QEvent.Type.ContextMenu, QEvent.Type.MouseMove)
