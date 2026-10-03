"""Give palette colors UI roles (background, text, primary, ...) for mockups.

Rules, in order: the background is the lightest color (darkest in dark mode); text is
a dark (light) palette color that reaches WCAG AA (4.5:1) on it, furthest from it in
lightness, falling back to near-black/near-white (mid-tones stay brand colors); primary, secondary and accent are the most
chromatic remaining colors, picked so their hues differ; on-color text is white or
near-black, whichever contrasts more. Surface, muted text and borders are mixed from
background and text so they always sit between them.
"""

from dataclasses import dataclass, field

from colorize.core.color import normalize_hex, to_oklch
from colorize.core.contrast import contrast_ratio
from colorize.core.mix import mix

ROLES = ("background", "surface", "border", "text", "muted", "primary", "secondary", "accent")
ROLE_LABELS = {
    "background": "Background",
    "surface": "Surface",
    "border": "Border",
    "text": "Text",
    "muted": "Muted text",
    "primary": "Primary",
    "secondary": "Secondary",
    "accent": "Accent",
}
CHROMATIC = 0.04  # OKLCH chroma below this counts as a neutral
TEXT_CONTRAST = 4.5
LARGE_TEXT_CONTRAST = 3.0
LIGHT_TEXT, DARK_TEXT = "#FFFFFF", "#141414"
CHART_COLORS = 6
TEXT_MAX_LIGHTNESS = 0.45  # body text should read as dark (light mode) ...
TEXT_MIN_LIGHTNESS_DARK = 0.85  # ... or as light (dark mode)


@dataclass(frozen=True)
class RoleSet:
    colors: dict[str, str]
    chart: tuple[str, ...]
    from_palette: frozenset[str] = field(default_factory=frozenset)  # roles taken directly from the palette

    def on(self, role: str) -> str:
        """Text color to put on a fill of ``role``."""
        fill = self.colors[role]
        return LIGHT_TEXT if contrast_ratio(LIGHT_TEXT, fill) >= contrast_ratio(DARK_TEXT, fill) else DARK_TEXT

    def contrast_problems(self) -> list[str]:
        """Text pairings the mockups use that miss WCAG AA: 4.5:1 for normal text,
        3:1 for large text (the primary-colored headline)."""
        checks = [
            ("Text on background", self.colors["text"], self.colors["background"], TEXT_CONTRAST),
            ("Text on surface", self.colors["text"], self.colors["surface"], TEXT_CONTRAST),
            ("Muted text on surface", self.colors["muted"], self.colors["surface"], TEXT_CONTRAST),
            ("Primary headline on background", self.colors["primary"], self.colors["background"], LARGE_TEXT_CONTRAST),
            ("Primary link on background", self.colors["primary"], self.colors["background"], TEXT_CONTRAST),
            ("Secondary link on background", self.colors["secondary"], self.colors["background"], TEXT_CONTRAST),
        ]
        checks += [
            (f"Label on {ROLE_LABELS[fill].lower()}", self.on(fill), self.colors[fill], TEXT_CONTRAST)
            for fill in ("primary", "secondary", "accent")
        ]
        problems = []
        for label, text, fill, minimum in checks:
            ratio = contrast_ratio(text, fill)
            if ratio < minimum:
                problems.append(f"{label}: {ratio:.2f}:1 (needs {minimum:g}:1)")
        return problems


def _hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def assign_roles(colors, dark: bool = False, rotation: int = 0, overrides=None) -> RoleSet:
    """``rotation`` cycles which chromatic colors become primary/secondary/accent
    (the Shuffle button); ``overrides`` pins roles to chosen colors."""
    seen, unique = set(), []
    for color in colors:
        color = normalize_hex(color)
        if color not in seen:
            seen.add(color)
            unique.append(color)
    lch = {c: to_oklch(c) for c in unique}
    overrides = {k: normalize_hex(v) for k, v in (overrides or {}).items() if k in ROLES}
    from_palette = set()

    # Background: the lightest (dark mode: darkest) color if it is light (dark) enough.
    ordered = sorted(unique, key=lambda c: lch[c][0], reverse=not dark)
    candidates = [c for c in ordered if (lch[c][0] >= 0.85 if not dark else lch[c][0] <= 0.25)]
    background = overrides.get("background") or (candidates[0] if candidates else ("#121212" if dark else "#FFFFFF"))
    if background in unique:
        from_palette.add("background")

    # Text: furthest in lightness from the background among colors that reach AA.
    def text_like(c: str) -> bool:
        return lch[c][0] >= TEXT_MIN_LIGHTNESS_DARK if dark else lch[c][0] <= TEXT_MAX_LIGHTNESS

    readable = [
        c for c in unique if c != background and text_like(c) and contrast_ratio(c, background) >= TEXT_CONTRAST
    ]
    readable.sort(key=lambda c: abs(lch[c][0] - to_oklch(background)[0]), reverse=True)
    fallback_text = LIGHT_TEXT if dark else DARK_TEXT
    text = overrides.get("text") or (readable[0] if readable else fallback_text)
    if text in unique:
        from_palette.add("text")

    # Brand colors: most chromatic first, rotated by Shuffle, hues kept apart.
    chromatic = sorted(
        (c for c in unique if c not in (background, text) and lch[c][1] >= CHROMATIC),
        key=lambda c: lch[c][1],
        reverse=True,
    )
    if chromatic:
        shift = rotation % len(chromatic)
        chromatic = chromatic[shift:] + chromatic[:shift]
    primary = overrides.get("primary") or (chromatic[0] if chromatic else text)
    rest = [c for c in chromatic if c != primary]
    hue = to_oklch(primary)[2]
    secondary = overrides.get("secondary") or next(
        (c for c in rest if _hue_gap(lch[c][2], hue) >= 25), rest[0] if rest else mix(primary, background, 0.35)
    )
    rest = [c for c in rest if c != secondary]
    accent = overrides.get("accent") or (
        max(rest, key=lambda c: _hue_gap(lch[c][2], hue)) if rest else secondary
    )
    for role, color in (("primary", primary), ("secondary", secondary), ("accent", accent)):
        if color in unique:
            from_palette.add(role)

    roles = {
        "background": background,
        "surface": overrides.get("surface") or mix(background, text, 0.05),
        "border": overrides.get("border") or mix(background, text, 0.14),
        "text": text,
        "muted": overrides.get("muted") or mix(text, background, 0.38),
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
    }
    for role in ("surface", "border", "muted"):
        if role in overrides and overrides[role] in unique:
            from_palette.add(role)
    chart = tuple((chromatic or unique or [primary])[:CHART_COLORS])
    return RoleSet(roles, chart, frozenset(from_palette))
