"""Color mixing and gradients.

OKLab mixes along a perceptually straight line, so blue + yellow passes through a
clean green-gray instead of the dull gray an sRGB mix gives; OKLCH keeps chroma and
walks the hue the shorter way round. sRGB (gamma-encoded, the CSS default) is
offered for comparison.
"""

from colorize.core.color import (
    hex_to_rgb,
    linear_srgb_to_oklab,
    normalize_hex,
    oklab_to_oklch,
    srgb_to_linear,
    to_oklch,
)
from colorize.core.gamut import map_to_srgb

INTERPOLATIONS = ("oklab", "oklch", "srgb")
INTERPOLATION_LABELS = {"oklab": "OKLab", "oklch": "OKLCH (shorter hue)", "srgb": "sRGB (CSS default, for comparison)"}


def _oklab(hex_color: str) -> tuple[float, float, float]:
    return linear_srgb_to_oklab(*(srgb_to_linear(c / 255) for c in hex_to_rgb(hex_color)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(a: str, b: str, t: float, space: str = "oklab") -> str:
    """Color ``t`` of the way from ``a`` to ``b`` (0..1). Endpoints come back unchanged."""
    a, b = normalize_hex(a), normalize_hex(b)
    if t <= 0:
        return a
    if t >= 1:
        return b
    if space == "srgb":
        channels = (round(_lerp(x, y, t)) for x, y in zip(hex_to_rgb(a), hex_to_rgb(b)))
        return "#{:02X}{:02X}{:02X}".format(*channels)
    if space == "oklab":
        lab = tuple(_lerp(x, y, t) for x, y in zip(_oklab(a), _oklab(b)))
        return map_to_srgb(*oklab_to_oklch(*lab)).hex
    if space == "oklch":
        (l1, c1, h1), (l2, c2, h2) = to_oklch(a), to_oklch(b)
        if c1 < 1e-4:  # a gray has no hue of its own: borrow the other end's
            h1 = h2
        if c2 < 1e-4:
            h2 = h1
        delta = (h2 - h1 + 180) % 360 - 180  # shorter way round
        return map_to_srgb(_lerp(l1, l2, t), _lerp(c1, c2, t), (h1 + delta * t) % 360).hex
    raise ValueError(f"unknown interpolation space: {space!r}")


def gradient(stops, count: int, space: str = "oklab") -> list[str]:
    """``count`` colors evenly along stops that are themselves evenly spaced."""
    stops = [normalize_hex(s) for s in stops]
    if len(stops) < 2 or count < 2:
        raise ValueError("need at least 2 stops and 2 colors")
    colors = []
    segments = len(stops) - 1
    for i in range(count):
        position = i / (count - 1) * segments
        segment = min(int(position), segments - 1)
        colors.append(mix(stops[segment], stops[segment + 1], position - segment, space))
    return colors


def css_linear_gradient(stops, space: str = "oklab", angle: int = 90) -> str:
    """CSS Color 4 gradient that browsers interpolate in the same space."""
    method = "" if space == "srgb" else f" in {space}"
    colors = ", ".join(normalize_hex(s).lower() for s in stops)
    return f"linear-gradient({angle}deg{method}, {colors})"
