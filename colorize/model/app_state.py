"""App-wide state that is not part of any document.

Like Photoshop, foreground/background colors and the active tool are global and
are not recorded in the undo history.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from colorize.core.color import normalize_hex

TOOL_KEYS = ("select", "eyedropper", "harmony", "extract", "contrast", "cvd", "hand", "zoom")


class AppState(QObject):
    colorsChanged = pyqtSignal()
    toolChanged = pyqtSignal(str)

    DEFAULT_FOREGROUND = "#000000"
    DEFAULT_BACKGROUND = "#FFFFFF"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._foreground = self.DEFAULT_FOREGROUND
        self._background = self.DEFAULT_BACKGROUND
        self._tool = "select"

    @property
    def foreground(self) -> str:
        return self._foreground

    @property
    def background(self) -> str:
        return self._background

    @property
    def tool(self) -> str:
        return self._tool

    def set_foreground(self, color: str) -> None:
        color = normalize_hex(color)
        if color != self._foreground:
            self._foreground = color
            self.colorsChanged.emit()

    def set_background(self, color: str) -> None:
        color = normalize_hex(color)
        if color != self._background:
            self._background = color
            self.colorsChanged.emit()

    def swap_colors(self) -> None:
        self._foreground, self._background = self._background, self._foreground
        self.colorsChanged.emit()

    def reset_colors(self) -> None:
        self._foreground = self.DEFAULT_FOREGROUND
        self._background = self.DEFAULT_BACKGROUND
        self.colorsChanged.emit()

    def set_tool(self, key: str) -> None:
        if key not in TOOL_KEYS:
            raise ValueError(f"unknown tool: {key!r}")
        if key != self._tool:
            self._tool = key
            self.toolChanged.emit(key)
