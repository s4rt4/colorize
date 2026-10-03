"""App-wide state that is not part of any document.

Like Photoshop, foreground/background colors and the active tool are global and
are not recorded in the undo history.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from colorize.core.color import normalize_hex

TOOL_KEYS = ("select", "eyedropper", "harmony", "extract", "contrast", "cvd", "hand", "zoom")
SAMPLE_SIZES = (1, 3, 5)  # eyedropper: point, 3x3 and 5x5 average
EXTRACT_COUNT_RANGE = (2, 16)


class AppState(QObject):
    colorsChanged = pyqtSignal()
    toolChanged = pyqtSignal(str)
    sampleSizeChanged = pyqtSignal(int)
    extractCountChanged = pyqtSignal(int)

    DEFAULT_FOREGROUND = "#000000"
    DEFAULT_BACKGROUND = "#FFFFFF"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._foreground = self.DEFAULT_FOREGROUND
        self._background = self.DEFAULT_BACKGROUND
        self._tool = "select"
        self._sample_size = 1
        self._extract_count = 5

    @property
    def foreground(self) -> str:
        return self._foreground

    @property
    def background(self) -> str:
        return self._background

    @property
    def tool(self) -> str:
        return self._tool

    @property
    def sample_size(self) -> int:
        return self._sample_size

    @property
    def extract_count(self) -> int:
        return self._extract_count

    def set_sample_size(self, size: int) -> None:
        if size not in SAMPLE_SIZES:
            raise ValueError(f"sample size must be one of {SAMPLE_SIZES}")
        if size != self._sample_size:
            self._sample_size = size
            self.sampleSizeChanged.emit(size)

    def set_extract_count(self, count: int) -> None:
        low, high = EXTRACT_COUNT_RANGE
        count = max(low, min(count, high))
        if count != self._extract_count:
            self._extract_count = count
            self.extractCountChanged.emit(count)

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
