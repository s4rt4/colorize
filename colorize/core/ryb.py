"""Artist's (RYB) color wheel as a remapping of OKLCH hue.

On the painter's wheel red/yellow/blue are primaries, so complements are red-green,
yellow-purple and blue-orange (what Adobe Color's default wheel does). Positions on
that wheel map piecewise-linearly to OKLCH hues through six anchor colors; everything
else (lightness, chroma, gamut mapping) stays in OKLCH.
"""

import numpy as np

# (RYB wheel angle, OKLCH hue of the anchor color)
ANCHORS = (
    (0.0, 29.2),  # red     #FF0000
    (60.0, 52.6),  # orange  #FF7F00
    (120.0, 109.8),  # yellow  #FFFF00
    (180.0, 142.5),  # green   #00FF00
    (240.0, 264.1),  # blue    #0000FF
    (300.0, 328.4),  # purple  #800080
    (360.0, 389.2),  # red again, one turn later
)
_RYB = np.array([a for a, _ in ANCHORS])
_HUE = np.array([h for _, h in ANCHORS])


def ryb_to_oklch_hue(angle):
    """Wheel angle (degrees, any range) -> OKLCH hue in [0, 360). Works on arrays too."""
    return np.interp(np.mod(angle, 360.0), _RYB, _HUE) % 360.0


def oklch_hue_to_ryb(hue):
    """OKLCH hue -> wheel angle in [0, 360). Inverse of ryb_to_oklch_hue."""
    # Shift into the anchors' range [29.2, 389.2) before interpolating.
    shifted = (np.asarray(hue, dtype=float) - _HUE[0]) % 360.0 + _HUE[0]
    return np.interp(shifted, _HUE, _RYB) % 360.0


WHEELS = ("oklch", "ryb")
WHEEL_LABELS = {"oklch": "Perceptual (OKLCH)", "ryb": "Artist (RYB)"}


def to_wheel(hue: float, wheel: str) -> float:
    """OKLCH hue -> angle on the given wheel."""
    return float(oklch_hue_to_ryb(hue)) if wheel == "ryb" else hue % 360.0


def from_wheel(angle: float, wheel: str) -> float:
    """Angle on the given wheel -> OKLCH hue."""
    return float(ryb_to_oklch_hue(angle)) if wheel == "ryb" else angle % 360.0
