"""Single-color helpers. Pure functions: no Qt, safe to test headless.

The sRGB <-> OKLab math is written out here (Björn Ottosson's matrices) instead of going
through coloraide: importing coloraide costs ~0.5 s at startup, and these conversions
run constantly. coloraide is still used, lazily, where its algorithms matter (CSS gamut
mapping, HSL, Lab), and the tests check this module against it.
"""

import math
import re

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# Below this chroma a color is treated as gray: its hue is meaningless and reported as 0.
ACHROMATIC_CHROMA = 2e-6


def normalize_hex(value: str) -> str:
    """Return ``value`` as ``#RRGGBB`` (uppercase). Accepts 3 or 6 digits, with or without ``#``."""
    match = _HEX_RE.match(value.strip())
    if not match:
        raise ValueError(f"not a hex color: {value!r}")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return "#" + digits.upper()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    digits = normalize_hex(value)[1:]
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    for channel in (r, g, b):
        if not 0 <= channel <= 255:
            raise ValueError(f"channel out of range 0-255: {channel}")
    return f"#{r:02X}{g:02X}{b:02X}"


# ------------------------------------------------------------ sRGB transfer


def srgb_to_linear(c: float) -> float:
    sign = -1.0 if c < 0 else 1.0
    c = abs(c)
    return sign * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: float) -> float:
    """Sign-preserving, so out-of-gamut values stay measurable."""
    sign = -1.0 if c < 0 else 1.0
    c = abs(c)
    return sign * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


# ------------------------------------------------------------------- OKLab


def linear_srgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_linear_srgb(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )


def oklab_to_oklch(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    chroma = math.hypot(a, b)
    if chroma < ACHROMATIC_CHROMA:
        return lightness, 0.0, 0.0
    return lightness, chroma, math.degrees(math.atan2(b, a)) % 360


def oklch_to_oklab(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    angle = math.radians(hue)
    return lightness, chroma * math.cos(angle), chroma * math.sin(angle)


def to_oklch(value: str) -> tuple[float, float, float]:
    """Return (lightness 0-1, chroma, hue in degrees). Achromatic colors get hue 0."""
    linear = (srgb_to_linear(c / 255) for c in hex_to_rgb(value))
    return oklab_to_oklch(*linear_srgb_to_oklab(*linear))


def format_oklch(value: str) -> str:
    lightness, chroma, hue = to_oklch(value)
    return f"oklch({lightness * 100:.1f}% {chroma:.3f} {hue:.1f})"
