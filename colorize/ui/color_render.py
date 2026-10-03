"""NumPy-rendered color fields as QImages, plus a shared swatch painter.

Out-of-gamut areas are shown dimmed toward the panel background, so the sRGB
gamut boundary is visible right on the wheel/plane.
"""

from functools import lru_cache

import numpy as np
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QImage, QPainter

from colorize.core.gamut import MAX_SRGB_CHROMA
from colorize.core.oklab import lch_to_ab, oklab_to_srgb8

OUT_OF_GAMUT_OPACITY = 0.35


def paint_swatch(p: QPainter, rect: QRect, color, border) -> None:
    """Bordered color square built from two fills, so the edge stays exact at
    fractional display scaling (a 1px drawRect can leave a sliver of fill outside it)."""
    p.fillRect(rect, QColor(border))
    p.fillRect(rect.adjusted(1, 1, -1, -1), QColor(color))


def _to_qimage(rgb8: np.ndarray, alpha8: np.ndarray | None, dpr: float) -> QImage:
    h, w, _ = rgb8.shape
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = rgb8
    rgba[..., 3] = 255 if alpha8 is None else alpha8
    image = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    image.setDevicePixelRatio(dpr)
    return image


def _dim_outside(rgb8: np.ndarray, inside: np.ndarray, bg: QColor) -> np.ndarray:
    bg8 = np.array([bg.red(), bg.green(), bg.blue()], dtype=np.float32)
    dimmed = (rgb8 * np.float32(OUT_OF_GAMUT_OPACITY) + bg8 * np.float32(1 - OUT_OF_GAMUT_OPACITY)).astype(np.uint8)
    return np.where(inside[..., None], rgb8, dimmed)


@lru_cache(maxsize=4)
def _wheel_grid(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-pixel OKLab a/b for the disc (independent of lightness) and the rim alpha."""
    center = (n - 1) / 2
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    dx, dy = xs - center, center - ys
    radius = np.hypot(dx, dy) / center
    hue = np.degrees(np.arctan2(dy, dx))
    a, b = lch_to_ab(np.minimum(radius, 1.0) * MAX_SRGB_CHROMA, hue)
    edge_px = (1.0 - radius) * center  # distance inside the rim, for an anti-aliased edge
    alpha8 = (np.clip(edge_px + 0.5, 0.0, 1.0) * 255).astype(np.uint8)
    return a, b, alpha8


def wheel_image(side: int, dpr: float, lightness: float, bg: QColor) -> QImage:
    """OKLCH hue/chroma disc at one lightness: angle = hue (0° at 3 o'clock,
    counter-clockwise), radius = chroma from 0 to MAX_SRGB_CHROMA."""
    n = max(2, round(side * dpr))
    a, b, alpha8 = _wheel_grid(n)
    rgb8, inside = oklab_to_srgb8(lightness, a, b)
    return _to_qimage(_dim_outside(rgb8, inside, bg), alpha8, dpr)


def plane_image(width: int, height: int, dpr: float, hue: float, bg: QColor) -> QImage:
    """Picker plane at one hue: x = chroma 0..MAX_SRGB_CHROMA, y = lightness 1 (top) .. 0."""
    w, h = max(2, round(width * dpr)), max(2, round(height * dpr))
    a, b = lch_to_ab(np.linspace(0.0, MAX_SRGB_CHROMA, w, dtype=np.float32)[None, :], hue)
    lightness = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None]
    rgb8, inside = oklab_to_srgb8(lightness, a, b)
    return _to_qimage(_dim_outside(rgb8, inside, bg), None, dpr)


HUE_STRIP_LIGHTNESS = 0.72
HUE_STRIP_CHROMA = 0.13


def hue_strip_image(width: int, height: int, dpr: float) -> QImage:
    """Vertical hue ramp, 0° at top to 360° at bottom, at a lightness/chroma that sRGB
    can show for (almost) every hue."""
    w, h = max(1, round(width * dpr)), max(2, round(height * dpr))
    a, b = lch_to_ab(HUE_STRIP_CHROMA, np.linspace(0.0, 360.0, h, dtype=np.float32)[:, None])
    rgb8, _ = oklab_to_srgb8(HUE_STRIP_LIGHTNESS, a * np.ones((1, w), np.float32), b * np.ones((1, w), np.float32))
    return _to_qimage(rgb8, None, dpr)
