"""Color books (named reference colors) and nearest matches by CIEDE2000.

Proprietary books (Pantone, RAL, ...) are licensed, so none ship with Colorize; users
import their own (.ase / .gpl, names kept). The one built-in book is the CSS named
colors, which are public (CSS Color Module Level 4).
"""

from dataclasses import dataclass, field

import numpy as np

from colorize.core.color import normalize_hex
from colorize.core.delta_e import hex_to_lab

CSS_BOOK_ID = 0  # built-in, not stored in the library


@dataclass(frozen=True)
class BookColor:
    name: str
    hex: str


@dataclass(frozen=True)
class BookMatch:
    color: BookColor
    delta_e: float


@dataclass
class ColorBook:
    id: int
    name: str
    colors: list[BookColor]
    _labs: np.ndarray | None = field(default=None, repr=False)

    @property
    def labs(self) -> np.ndarray:
        if self._labs is None:
            self._labs = np.array([hex_to_lab(c.hex) for c in self.colors], dtype=np.float64).reshape(-1, 3)
        return self._labs

    def nearest(self, hex_color: str, count: int = 1) -> list[BookMatch]:
        if not self.colors:
            return []
        distances = delta_e_2000_many(hex_to_lab(normalize_hex(hex_color)), self.labs)
        order = np.argsort(distances, kind="stable")[:count]
        return [BookMatch(self.colors[i], float(distances[i])) for i in order]


def css_named_book() -> ColorBook:
    from coloraide.css.color_names import name2val_map  # only needed when the book is used

    colors = [
        BookColor(name, "#{:02X}{:02X}{:02X}".format(*(int(v) for v in rgba[:3])))
        for name, rgba in sorted(name2val_map.items())
        if rgba[3] == 255  # skip "transparent"
    ]
    return ColorBook(CSS_BOOK_ID, "CSS Named Colors", colors)


def delta_e_2000_many(lab: tuple[float, float, float], labs: np.ndarray) -> np.ndarray:
    """CIEDE2000 from one Lab color to each row of ``labs`` (N, 3); same formula as
    core.delta_e.delta_e_2000, vectorized for searching large books."""
    l1, a1, b1 = lab
    l2, a2, b2 = labs[:, 0], labs[:, 1], labs[:, 2]
    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(c_bar**7 / (c_bar**7 + 25.0**7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, np.degrees(np.arctan2(b1, a1p)) % 360)
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, np.degrees(np.arctan2(b2, a2p)) % 360)

    dlp = l2 - l1
    dcp = c2p - c1p
    zero = c1p * c2p == 0
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, np.where(dhp < -180, dhp + 360, dhp))
    dhp = np.where(zero, 0.0, dhp)
    dhp_big = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp / 2))

    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    hsum = h1p + h2p
    hp_bar = np.where(
        zero,
        hsum,
        np.where(np.abs(h1p - h2p) <= 180, hsum / 2, np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    t = (
        1
        - 0.17 * np.cos(np.radians(hp_bar - 30))
        + 0.24 * np.cos(np.radians(2 * hp_bar))
        + 0.32 * np.cos(np.radians(3 * hp_bar + 6))
        - 0.20 * np.cos(np.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * np.exp(-(((hp_bar - 275) / 25) ** 2))
    rc = 2 * np.sqrt(cp_bar**7 / (cp_bar**7 + 25.0**7))
    sl = 1 + 0.015 * (lp_bar - 50) ** 2 / np.sqrt(20 + (lp_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -np.sin(np.radians(2 * d_theta)) * rc
    return np.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp_big / sh) ** 2 + rt * (dcp / sc) * (dhp_big / sh)
    )
