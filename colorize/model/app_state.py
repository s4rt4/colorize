"""App-wide state that is not part of any document.

Like Photoshop, foreground/background colors and the active tool are global and
are not recorded in the undo history.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from colorize.core.color import normalize_hex
from colorize.core.contrast import APCA_TARGETS, METHODS, WCAG_TARGETS
from colorize.core.cvd import CVD_TYPES, simulate_hex_cached

TOOL_KEYS = ("select", "eyedropper", "harmony", "extract", "contrast", "cvd", "hand", "zoom")
SAMPLE_SIZES = (1, 3, 5)  # eyedropper: point, 3x3 and 5x5 average
EXTRACT_COUNT_RANGE = (2, 16)
DEFAULT_TARGETS = {"wcag": "aa", "apca": "lc75"}


class AppState(QObject):
    colorsChanged = pyqtSignal()
    toolChanged = pyqtSignal(str)
    sampleSizeChanged = pyqtSignal(int)
    extractCountChanged = pyqtSignal(int)
    contrastChanged = pyqtSignal()
    cvdChanged = pyqtSignal()
    proofChanged = pyqtSignal(bool)

    DEFAULT_FOREGROUND = "#000000"
    DEFAULT_BACKGROUND = "#FFFFFF"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._foreground = self.DEFAULT_FOREGROUND
        self._background = self.DEFAULT_BACKGROUND
        self._tool = "select"
        self._sample_size = 1
        self._extract_count = 5
        self._contrast_method = "wcag"
        self._contrast_target = "aa"
        self._cvd_type = "deutan"  # the most common form
        self._cvd_severity = 1.0
        self._proof = False

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

    @property
    def contrast_method(self) -> str:
        return self._contrast_method

    @property
    def contrast_target(self) -> str:
        return self._contrast_target

    def set_contrast(self, method: str, target: str | None = None) -> None:
        """Change the checking method; a method change resets the target to its default."""
        if method not in METHODS:
            raise ValueError(f"unknown contrast method: {method!r}")
        targets = WCAG_TARGETS if method == "wcag" else APCA_TARGETS
        if target is None or target not in targets:
            target = self._contrast_target if method == self._contrast_method else DEFAULT_TARGETS[method]
        if (method, target) != (self._contrast_method, self._contrast_target):
            self._contrast_method, self._contrast_target = method, target
            self.contrastChanged.emit()

    @property
    def cvd_type(self) -> str:
        return self._cvd_type

    @property
    def cvd_severity(self) -> float:
        return self._cvd_severity

    def set_cvd(self, kind: str | None = None, severity: float | None = None) -> None:
        kind = self._cvd_type if kind is None else kind
        if kind not in CVD_TYPES:
            raise ValueError(f"unknown color vision type: {kind!r}")
        severity = self._cvd_severity if severity is None else min(max(severity, 0.0), 1.0)
        if (kind, severity) != (self._cvd_type, self._cvd_severity):
            self._cvd_type, self._cvd_severity = kind, severity
            self.cvdChanged.emit()

    @property
    def proof(self) -> bool:
        return self._proof

    def set_proof(self, on: bool) -> None:
        if on != self._proof:
            self._proof = on
            self.proofChanged.emit(on)

    def proof_filter(self):
        """hex -> hex function for canvases while proofing, else None."""
        if not self._proof:
            return None
        kind, severity = self._cvd_type, self._cvd_severity
        return lambda hex_color: simulate_hex_cached(hex_color, kind, severity)

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
