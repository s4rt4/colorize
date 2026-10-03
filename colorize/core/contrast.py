"""Text contrast: WCAG 2.x ratio, APCA lightness contrast, and fixes that pass a target.

WCAG 2.x is the conformance standard. APCA (APCA-W3 0.0.98G-4g constants, the WCAG 3
working draft candidate) is shown as guidance only; it is not a conformance metric.
"""

import math
from dataclasses import dataclass

from colorize.core.color import hex_to_rgb, to_oklch
from colorize.core.gamut import map_to_srgb

# ------------------------------------------------------------------ WCAG 2.x

WCAG_TARGETS = {
    "aa": ("AA", 4.5),
    "aa_large": ("AA Large", 3.0),
    "aaa": ("AAA", 7.0),
    "aaa_large": ("AAA Large", 4.5),
}
WCAG_NON_TEXT = 3.0  # 1.4.11 non-text contrast (UI components, graphics)


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    r, g, b = (_linear(c) for c in hex_to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio, 1 to 21 (order does not matter)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def format_ratio(ratio: float) -> str:
    """Two decimals, truncated: WCAG compares unrounded, so 4.499 must never show as 4.50."""
    return f"{math.floor(ratio * 100) / 100:.2f}:1"


# ---------------------------------------------------------------------- APCA

_APCA_EXP = 2.4
_APCA_RGB = (0.2126729, 0.7151522, 0.0721750)
_NORM_BG, _NORM_TXT, _REV_TXT, _REV_BG = 0.56, 0.57, 0.62, 0.65
_BLK_THRS, _BLK_CLMP = 0.022, 1.414
_SCALE = 1.14
_LO_OFFSET = 0.027
_DELTA_Y_MIN = 0.0005
_LO_CLIP = 0.1

# Bronze-level guidance (positive and negative polarity alike use |Lc|).
APCA_TARGETS = {
    "lc90": ("Lc 90 · preferred body text", 90),
    "lc75": ("Lc 75 · body text", 75),
    "lc60": ("Lc 60 · content text", 60),
    "lc45": ("Lc 45 · large text, headlines", 45),
    "lc30": ("Lc 30 · non-text, placeholder", 30),
}


def _apca_y(hex_color: str) -> float:
    y = sum(k * (c / 255) ** _APCA_EXP for k, c in zip(_APCA_RGB, hex_to_rgb(hex_color)))
    return y + (_BLK_THRS - y) ** _BLK_CLMP if y < _BLK_THRS else y


def apca_contrast(text: str, background: str) -> float:
    """Lightness contrast Lc: positive for dark text on light, negative for light on dark."""
    y_text, y_bg = _apca_y(text), _apca_y(background)
    if abs(y_bg - y_text) < _DELTA_Y_MIN:
        return 0.0
    if y_bg > y_text:
        sapc = (y_bg**_NORM_BG - y_text**_NORM_TXT) * _SCALE
        out = 0.0 if sapc < _LO_CLIP else sapc - _LO_OFFSET
    else:
        sapc = (y_bg**_REV_BG - y_text**_REV_TXT) * _SCALE
        out = 0.0 if sapc > -_LO_CLIP else sapc + _LO_OFFSET
    return out * 100


def apca_guidance(lc: float) -> str:
    """Plain-language use for an Lc value (APCA bronze simple mode)."""
    magnitude = abs(lc)
    for _key, (label, minimum) in APCA_TARGETS.items():
        if magnitude >= minimum:
            return label.split(" · ", 1)[1].capitalize() + " OK"
    return "Too low for text"


# ------------------------------------------------------------- suggestions

METHODS = ("wcag", "apca")


def target_value(method: str, target: str) -> float:
    return (WCAG_TARGETS if method == "wcag" else APCA_TARGETS)[target][1]


def score(method: str, text: str, background: str) -> float:
    """Comparable 'more is better' number for either method."""
    return contrast_ratio(text, background) if method == "wcag" else abs(apca_contrast(text, background))


def passes(method: str, target: str, text: str, background: str) -> bool:
    return score(method, text, background) >= target_value(method, target)


@dataclass(frozen=True)
class Suggestion:
    hex: str
    direction: str  # "darker" or "lighter"
    lightness_change: float  # OKLCH lightness delta, signed


def suggest_text_colors(method: str, target: str, text: str, background: str) -> list[Suggestion]:
    """Closest text colors (one darker, one lighter when possible) that meet the target.

    Only OKLCH lightness moves; hue is kept and chroma is reduced just enough to stay in
    sRGB. Bisection assumes contrast grows monotonically as text moves away from the
    background in lightness, which holds for a fixed background.
    """
    lightness, chroma, hue = to_oklch(text)
    goal = target_value(method, target)

    def color_at(level: float) -> str:
        return map_to_srgb(level, chroma, hue).hex

    def ok(level: float) -> bool:
        return score(method, color_at(level), background) >= goal

    suggestions = []
    for direction, end in (("darker", 0.0), ("lighter", 1.0)):
        if not ok(end):
            continue
        near, far = lightness, end  # near fails (or is the start), far passes
        if ok(near):
            continue  # already passing; no change needed in this direction
        for _ in range(30):
            mid = (near + far) / 2
            if ok(mid):
                far = mid
            else:
                near = mid
        hex_color = color_at(far)
        suggestions.append(Suggestion(hex_color, direction, far - lightness))
    suggestions.sort(key=lambda s: abs(s.lightness_change))
    return suggestions
