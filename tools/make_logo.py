"""Generate the Colorize logo: a rounded tile with a "C" whose hue sweeps the color wheel.

The hues are taken in OKLCH at one lightness/chroma, so every part of the C has the
same perceived brightness (an HSL rainbow would show bright yellow and dark blue bands).

    python tools/make_logo.py

Writes colorize/ui/assets/logo.svg and colorize/ui/assets/colorize.ico.
"""

import io
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from colorize.core.gamut import map_to_srgb, max_chroma  # noqa: E402

ASSETS = ROOT / "colorize" / "ui" / "assets"
SIZE = 512
TILE_RADIUS = 112  # rounded-square corners, roughly the app-tile proportion
TILE_COLOR = "#1F1F1F"
TILE_EDGE = "#383838"

RING_CENTER = (256, 256)
RING_RADIUS = 150
RING_WIDTH = 78
GAP_DEGREES = 76  # opening of the C, centered on the right
LIGHTNESS = 0.74
CHROMA = 0.17  # upper bound; each hue uses at most 95% of what sRGB can show (see _color)
HUE_START = 20  # hue at the top end of the C, sweeping counter-clockwise
SEGMENTS = 120


def _point(angle_deg: float, radius: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    cx, cy = RING_CENTER
    return cx + radius * math.cos(a), cy - radius * math.sin(a)


def _color(hue: float) -> str:
    """Chroma follows the sRGB boundary smoothly instead of being clipped per hue,
    which would leave visible seams where the boundary dips (cyan, blue)."""
    chroma = min(CHROMA, 0.95 * max_chroma(LIGHTNESS, hue))
    return map_to_srgb(LIGHTNESS, chroma, hue).hex


def _segment(start: float, end: float) -> str:
    """Annular sector between two angles (degrees, counter-clockwise)."""
    outer, inner = RING_RADIUS + RING_WIDTH / 2, RING_RADIUS - RING_WIDTH / 2
    x0, y0 = _point(start, outer)
    x1, y1 = _point(end, outer)
    x2, y2 = _point(end, inner)
    x3, y3 = _point(start, inner)
    return (
        f"M{x0:.2f} {y0:.2f} A{outer} {outer} 0 0 0 {x1:.2f} {y1:.2f} "
        f"L{x2:.2f} {y2:.2f} A{inner} {inner} 0 0 1 {x3:.2f} {y3:.2f}Z"
    )


def build_svg() -> str:
    first = GAP_DEGREES / 2  # just above the opening
    sweep = 360 - GAP_DEGREES
    step = sweep / SEGMENTS
    parts = []
    for i in range(SEGMENTS):
        start = first + i * step
        hue = HUE_START + (i + 0.5) / SEGMENTS * 300
        color = _color(hue)
        # Overlap slightly so anti-aliasing never shows seams between segments.
        parts.append(f'<path d="{_segment(start, start + step + 0.6)}" fill="{color}"/>')
    # Round caps at both ends of the C.
    for angle, hue in ((first, HUE_START), (first + sweep, HUE_START + 300)):
        x, y = _point(angle, RING_RADIUS)
        color = _color(hue)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{RING_WIDTH / 2}" fill="{color}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">\n'
        f'<rect x="8" y="8" width="{SIZE - 16}" height="{SIZE - 16}" rx="{TILE_RADIUS}" '
        f'fill="{TILE_COLOR}" stroke="{TILE_EDGE}" stroke-width="4"/>\n' + "\n".join(parts) + "\n</svg>\n"
    )


def render_png(svg: str, size: int) -> bytes:
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode()))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def main() -> None:
    from PIL import Image
    from PyQt6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841 (needed for rendering)
    ASSETS.mkdir(parents=True, exist_ok=True)
    svg = build_svg()
    (ASSETS / "logo.svg").write_text(svg, encoding="utf-8", newline="\n")
    big = Image.open(io.BytesIO(render_png(svg, 256)))
    big.save(ASSETS / "colorize.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {ASSETS / 'logo.svg'} and {ASSETS / 'colorize.ico'}")


if __name__ == "__main__":
    main()
