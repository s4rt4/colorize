"""sRGB gamut checks and mapping for single colors.

Mapping uses CSS Color 4 style chroma reduction in OKLCH (coloraide's
``oklch-chroma``): hue is kept and lightness barely moves, only chroma drops.
"""

from dataclasses import dataclass

from coloraide import Color

GAMUT_METHOD = "oklch-chroma"

# Largest OKLCH chroma any sRGB color reaches is about 0.322 (magenta); round up for UI scales.
MAX_SRGB_CHROMA = 0.33


@dataclass(frozen=True)
class MappedColor:
    hex: str  # displayable sRGB color, after gamut mapping if needed
    in_gamut: bool  # False when the requested OKLCH color was outside sRGB


def _oklch(lightness: float, chroma: float, hue: float) -> Color:
    return Color("oklch", [min(max(lightness, 0.0), 1.0), max(chroma, 0.0), hue % 360])


def in_srgb_gamut(lightness: float, chroma: float, hue: float) -> bool:
    return _oklch(lightness, chroma, hue).in_gamut("srgb")


def map_to_srgb(lightness: float, chroma: float, hue: float) -> MappedColor:
    color = _oklch(lightness, chroma, hue)
    inside = color.in_gamut("srgb")
    if not inside:
        color.fit("srgb", method=GAMUT_METHOD)
    return MappedColor(color.convert("srgb").to_string(hex=True).upper(), inside)


def max_chroma(lightness: float, hue: float) -> float:
    """Largest chroma still inside sRGB at exactly this lightness and hue.

    Bisection rather than ``fit``: the fit may nudge lightness/hue, which would
    not give the boundary at the requested ones.
    """
    low, high = 0.0, MAX_SRGB_CHROMA + 0.05
    if not in_srgb_gamut(lightness, low, hue):
        return 0.0
    for _ in range(24):
        mid = (low + high) / 2
        if in_srgb_gamut(lightness, mid, hue):
            low = mid
        else:
            high = mid
    return low
