"""Color harmony rules in OKLCH.

Hue rules rotate the base hue and keep its lightness and chroma, so every color has
the same perceived lightness and colorfulness (unlike HSL/RYB wheels). Monochromatic
keeps hue and chroma and steps lightness.

Results are in display order; ``base_index`` says which entry is the base color.
"""

from dataclasses import dataclass

RULES = ("complementary", "analogous", "triadic", "tetradic", "split", "monochromatic")

RULE_LABELS = {
    "complementary": "Complementary",
    "analogous": "Analogous",
    "triadic": "Triadic",
    "tetradic": "Tetradic",
    "split": "Split Complementary",
    "monochromatic": "Monochromatic",
}

# Hue offsets in degrees, in display order; 0 is the base.
HUE_OFFSETS = {
    "complementary": (0, 180),
    "analogous": (-60, -30, 0, 30, 60),
    "triadic": (0, 120, 240),
    "tetradic": (0, 90, 180, 270),
    "split": (150, 0, 210),
}

MONO_COUNT = 5
MONO_STEP = 0.12
MONO_RANGE = (0.12, 0.96)


@dataclass(frozen=True)
class Harmony:
    rule: str
    colors: tuple[tuple[float, float, float], ...]  # (lightness 0-1, chroma, hue degrees)
    base_index: int


def _mono_lightness(base: float) -> list[float]:
    """Base plus the MONO_COUNT-1 nearest steps of MONO_STEP that stay in MONO_RANGE."""
    low, high = MONO_RANGE
    span = MONO_COUNT
    candidates = [base + n * MONO_STEP for n in range(-span, span + 1) if n != 0]
    candidates = [v for v in candidates if low <= v <= high]
    nearest = sorted(candidates, key=lambda v: (abs(v - base), v))[: MONO_COUNT - 1]
    return sorted(nearest + [base])


def harmony(rule: str, lightness: float, chroma: float, hue: float) -> Harmony:
    if rule not in RULES:
        raise ValueError(f"unknown harmony rule: {rule!r}")
    hue %= 360
    if rule == "monochromatic":
        levels = _mono_lightness(lightness)
        colors = tuple((level, chroma, hue) for level in levels)
        return Harmony(rule, colors, levels.index(lightness))
    offsets = HUE_OFFSETS[rule]
    colors = tuple((lightness, chroma, (hue + offset) % 360) for offset in offsets)
    return Harmony(rule, colors, offsets.index(0))


def offset_of(rule: str, index: int) -> float:
    """Hue offset of color ``index`` from the base (0 for monochromatic)."""
    return 0.0 if rule == "monochromatic" else float(HUE_OFFSETS[rule][index])
