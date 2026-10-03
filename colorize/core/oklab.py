"""Vectorized OKLab/OKLCH -> sRGB for per-pixel rendering (wheel, picker planes).

Single colors go through coloraide (see gamut.py); this module exists because
coloraide is pure Python and far too slow per pixel. Matrices: Björn Ottosson, OKLab.
Math runs in float32: plenty for 8-bit display output and roughly twice as fast.
"""

import numpy as np

GAMUT_EPSILON = 1e-4
_LUT_SIZE = 16384  # linear -> 8-bit sRGB table; < 0.25 code value error at the dark end


def oklab_to_linear_srgb(lightness, a, b) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Broadcastable inputs; returns linear (r, g, b) arrays, possibly outside [0, 1]."""
    lightness = np.asarray(lightness, dtype=np.float32)
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    l_ = lightness + np.float32(0.3963377774) * a + np.float32(0.2158037573) * b
    m_ = lightness - np.float32(0.1055613458) * a - np.float32(0.0638541728) * b
    s_ = lightness - np.float32(0.0894841775) * a - np.float32(1.2914855480) * b
    l3, m3, s3 = l_ * l_ * l_, m_ * m_ * m_, s_ * s_ * s_
    red = np.float32(4.0767416621) * l3 - np.float32(3.3077115913) * m3 + np.float32(0.2309699292) * s3
    green = np.float32(-1.2684380046) * l3 + np.float32(2.6097574011) * m3 - np.float32(0.3413193965) * s3
    blue = np.float32(-0.0041960863) * l3 - np.float32(0.7034186147) * m3 + np.float32(1.7076147010) * s3
    return red, green, blue


def lch_to_ab(chroma, hue_deg) -> tuple[np.ndarray, np.ndarray]:
    hue = np.radians(np.asarray(hue_deg, dtype=np.float32))
    chroma = np.asarray(chroma, dtype=np.float32)
    return chroma * np.cos(hue), chroma * np.sin(hue)


def _in_gamut(red, green, blue) -> np.ndarray:
    lo, hi = -GAMUT_EPSILON, 1 + GAMUT_EPSILON
    return (red >= lo) & (red <= hi) & (green >= lo) & (green <= hi) & (blue >= lo) & (blue <= hi)


def encode_srgb(linear: np.ndarray) -> np.ndarray:
    """Linear-light to gamma-encoded sRGB floats (input clipped to [0, 1])."""
    x = np.clip(linear, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


_LUT = np.round(encode_srgb(np.linspace(0.0, 1.0, _LUT_SIZE)) * 255).astype(np.uint8)


def encode_srgb8(linear: np.ndarray) -> np.ndarray:
    """Linear-light to 8-bit sRGB through a lookup table (fast path for images)."""
    index = np.clip(linear, 0.0, 1.0) * np.float32(_LUT_SIZE - 1)
    return _LUT[(index + np.float32(0.5)).astype(np.int32)]


def oklab_to_srgb8(lightness, a, b) -> tuple[np.ndarray, np.ndarray]:
    """Return (uint8 sRGB with shape (..., 3), in-gamut mask with shape (...))."""
    red, green, blue = oklab_to_linear_srgb(lightness, a, b)
    rgb = np.stack([encode_srgb8(red), encode_srgb8(green), encode_srgb8(blue)], axis=-1)
    return rgb, _in_gamut(red, green, blue)


_DECODE = np.linspace(0.0, 1.0, 256)
_DECODE = np.where(_DECODE <= 0.04045, _DECODE / 12.92, ((_DECODE + 0.055) / 1.055) ** 2.4)


def decode_srgb8(rgb8: np.ndarray) -> np.ndarray:
    """8-bit sRGB to linear-light float64 (exact 256-entry table)."""
    return _DECODE[np.asarray(rgb8, dtype=np.uint8)]


def srgb8_to_oklab(rgb8: np.ndarray) -> np.ndarray:
    """(..., 3) uint8 sRGB to (..., 3) float64 OKLab. Float64 so cluster means of a
    flat color round-trip to the same hex."""
    linear = decode_srgb8(rgb8)
    r, g, b = linear[..., 0], linear[..., 1], linear[..., 2]
    l_ = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack(
        [
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ],
        axis=-1,
    )


def oklch_to_srgb(lightness, chroma, hue_deg) -> tuple[np.ndarray, np.ndarray]:
    """Return (clipped sRGB floats in [0, 1] with shape (..., 3), in-gamut mask).
    Exact (no lookup table); used where accuracy matters more than speed."""
    a, b = lch_to_ab(chroma, hue_deg)
    red, green, blue = oklab_to_linear_srgb(lightness, a, b)
    linear = np.stack(np.broadcast_arrays(red, green, blue), axis=-1).astype(np.float64)
    return encode_srgb(linear), _in_gamut(*np.broadcast_arrays(red, green, blue))
