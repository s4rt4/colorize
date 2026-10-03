"""Live harmony state: rule + base color kept as OKLCH floats.

The base is stored as floats (not hex) so dragging on the wheel is smooth and an
out-of-gamut base stays where the user put it; only the displayed colors are mapped.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from colorize.core.color import to_oklch
from colorize.core.gamut import MappedColor, map_to_srgb
from colorize.core.harmony import RULES, Harmony, harmony
from colorize.core.ryb import WHEELS


class HarmonyModel(QObject):
    changed = pyqtSignal()
    ruleChanged = pyqtSignal(str)
    wheelChanged = pyqtSignal(str)

    def __init__(self, rule: str = "complementary", base_hex: str = "#3D6A9E", parent=None):
        super().__init__(parent)
        self._rule = rule
        self._wheel = "oklch"
        self._base = to_oklch(base_hex)
        self._update()

    @property
    def rule(self) -> str:
        return self._rule

    @property
    def base(self) -> tuple[float, float, float]:
        return self._base

    @property
    def harmony(self) -> Harmony:
        return self._harmony

    @property
    def mapped(self) -> tuple[MappedColor, ...]:
        return self._mapped

    @property
    def base_mapped(self) -> MappedColor:
        return self._mapped[self._harmony.base_index]

    def hexes(self) -> list[str]:
        return [m.hex for m in self._mapped]

    def set_rule(self, rule: str) -> None:
        if rule not in RULES:
            raise ValueError(f"unknown harmony rule: {rule!r}")
        if rule != self._rule:
            self._rule = rule
            self._update()
            self.ruleChanged.emit(rule)

    @property
    def wheel(self) -> str:
        return self._wheel

    def set_wheel(self, wheel: str) -> None:
        if wheel not in WHEELS:
            raise ValueError(f"unknown wheel: {wheel!r}")
        if wheel != self._wheel:
            self._wheel = wheel
            self._update()
            self.wheelChanged.emit(wheel)

    def set_base_hex(self, hex_color: str) -> None:
        self._base = to_oklch(hex_color)
        self._update()

    def edit_base(self, lightness: float | None = None, chroma: float | None = None, hue: float | None = None) -> None:
        old_l, old_c, old_h = self._base
        new = (
            old_l if lightness is None else min(max(lightness, 0.0), 1.0),
            old_c if chroma is None else max(chroma, 0.0),
            old_h if hue is None else hue % 360,
        )
        if new != self._base:
            self._base = new
            self._update()

    def _update(self) -> None:
        self._harmony = harmony(self._rule, *self._base, wheel=self._wheel)
        self._mapped = tuple(map_to_srgb(*c) for c in self._harmony.colors)
        self.changed.emit()
