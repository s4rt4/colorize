"""sRGB gamut checks and mapping for single colors.

Mapping uses CSS Color 4 style chroma reduction in OKLCH (coloraide's
``oklch-chroma``): hue is kept and lightness barely moves, only chroma drops.
In-gamut colors (the common case) never touch coloraide; it is imported only when a
color actually needs mapping.
"""

from dataclasses import dataclass

from colorize.core.color import linear_to_srgb, oklab_to_linear_srgb, oklch_to_oklab

GAMUT_METHOD = "oklch-chroma"
# Same tolerance coloraide's in_gamut() applies to gamma-encoded sRGB channels.
GAMUT_TOLERANCE = 0.000075

# Largest OKLCH chroma any sRGB color reaches is about 0.322 (magenta); round up for UI scales.
MAX_SRGB_CHROMA = 0.33


@dataclass(frozen=True)
class MappedColor:
    hex: str  # displayable sRGB color, after gamut mapping if needed
    in_gamut: bool  # False when the requested OKLCH color was outside sRGB


def _clamp(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    return min(max(lightness, 0.0), 1.0), max(chroma, 0.0), hue % 360


def _srgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    """Gamma-encoded sRGB, unclipped (outside 0..1 when out of gamut)."""
    linear = oklab_to_linear_srgb(*oklch_to_oklab(*_clamp(lightness, chroma, hue)))
    return tuple(linear_to_srgb(c) for c in linear)


def _inside(rgb) -> bool:
    return all(-GAMUT_TOLERANCE <= c <= 1 + GAMUT_TOLERANCE for c in rgb)


def _hex(rgb) -> str:
    r, g, b = (int(min(max(c, 0.0), 1.0) * 255 + 0.5) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def in_srgb_gamut(lightness: float, chroma: float, hue: float) -> bool:
    return _inside(_srgb(lightness, chroma, hue))


def map_to_srgb(lightness: float, chroma: float, hue: float) -> MappedColor:
    rgb = _srgb(lightness, chroma, hue)
    if _inside(rgb):
        return MappedColor(_hex(rgb), True)
    from coloraide import Color  # slow import, only needed for out-of-gamut colors

    color = Color("oklch", list(_clamp(lightness, chroma, hue))).fit("srgb", method=GAMUT_METHOD)
    return MappedColor(color.convert("srgb").to_string(hex=True).upper(), False)


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
