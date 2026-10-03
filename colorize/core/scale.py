"""Tint/shade scales (50-950, Tailwind-style) with perceptually even lightness.

Lightness is spaced evenly in OKLCH (which is perceptually uniform), so the steps look
evenly spaced, unlike HSL scales that bunch up in the darks. The base color sits
exactly on the step whose even lightness is nearest to it; the steps above and below
are spread evenly between it and the ends of the range.

Chroma keeps the base color's *relative* chroma: its share of the most chroma sRGB
allows at that lightness and hue. Steps therefore stay in gamut and fade toward the
very light and very dark ends the way real tints and shades do.
"""

from dataclasses import dataclass

from colorize.core.color import normalize_hex, to_oklch
from colorize.core.gamut import map_to_srgb, max_chroma

SCALE_STEPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)
LIGHTEST = 0.97
DARKEST = 0.26


@dataclass(frozen=True)
class ScaleStep:
    step: int
    hex: str
    lightness: float
    is_base: bool


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if count == 1:
        return [start]
    return [start + (stop - start) * i / (count - 1) for i in range(count)]


def base_step_index(lightness: float, lightest: float = LIGHTEST, darkest: float = DARKEST) -> int:
    targets = _linspace(lightest, darkest, len(SCALE_STEPS))
    return min(range(len(targets)), key=lambda i: abs(targets[i] - lightness))


def tint_shade_scale(base: str, lightest: float = LIGHTEST, darkest: float = DARKEST) -> list[ScaleStep]:
    if not 0 <= darkest < lightest <= 1:
        raise ValueError("need 0 <= darkest < lightest <= 1")
    base = normalize_hex(base)
    lightness, chroma, hue = to_oklch(base)
    limit = max_chroma(lightness, hue)
    relative = min(chroma / limit, 1.0) if limit > 1e-9 else 0.0

    k = base_step_index(lightness, lightest, darkest)
    n = len(SCALE_STEPS)
    upper_end = max(lightest, lightness)  # a base lighter than the range becomes step 50 itself
    lower_end = min(darkest, lightness)
    levels = _linspace(upper_end, lightness, k + 1)[:-1] + [lightness] + _linspace(lightness, lower_end, n - k)[1:]

    steps = []
    for i, (step, level) in enumerate(zip(SCALE_STEPS, levels)):
        if i == k:
            steps.append(ScaleStep(step, base, lightness, True))
            continue
        step_chroma = relative * max_chroma(level, hue)
        steps.append(ScaleStep(step, map_to_srgb(level, step_chroma, hue).hex, level, False))
    return steps
