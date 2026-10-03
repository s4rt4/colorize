"""Single-color helpers. Pure functions: no Qt, safe to test headless."""

import math
import re

from coloraide import Color

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


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


def to_oklch(value: str) -> tuple[float, float, float]:
    """Return (lightness 0-1, chroma, hue in degrees). Achromatic colors get hue 0."""
    lightness, chroma, hue = Color(normalize_hex(value)).convert("oklch").coords()
    if math.isnan(hue):
        hue = 0.0
    return lightness, chroma, hue


def format_oklch(value: str) -> str:
    lightness, chroma, hue = to_oklch(value)
    return f"oklch({lightness * 100:.1f}% {chroma:.3f} {hue:.1f})"
