"""Text exports: color lists, CSS custom properties, Tailwind v4/v3, W3C design tokens.

Swatches have no names of their own, so every format names them ``<prefix>-<key>``:
keys are 1, 2, 3, ... or, for an 11-color tint/shade scale, 50, 100, ... 950.
The prefix defaults to the palette name.
"""

import json
import math
import re

from colorize.core.color import format_oklch, hex_to_rgb, normalize_hex

SCALE_KEYS = ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950")
NAMINGS = ("numbered", "scale")
NAMING_LABELS = {"numbered": "Numbered (1, 2, 3…)", "scale": "Scale (50 – 950)"}

SYNTAXES = ("hex", "rgb", "hsl", "oklch")
SYNTAX_LABELS = {"hex": "HEX", "rgb": "RGB", "hsl": "HSL", "oklch": "OKLCH"}


def slugify(name: str, fallback: str = "color") -> str:
    """CSS/JS-safe identifier: lowercase ASCII words joined by hyphens, never starting with a digit."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        return fallback
    return f"c-{slug}" if slug[0].isdigit() else slug


def format_color(hex_color: str, syntax: str) -> str:
    """One color in CSS Color 4 syntax (space-separated functions)."""
    hex_color = normalize_hex(hex_color)
    if syntax == "hex":
        return hex_color.lower()
    if syntax == "rgb":
        return "rgb({} {} {})".format(*hex_to_rgb(hex_color))
    if syntax == "hsl":
        from coloraide import Color  # slow import; only exports need HSL

        hue, saturation, lightness = Color(hex_color).convert("hsl").coords(nans=False)
        return f"hsl({_num(hue, 1)} {_num(saturation * 100, 1)}% {_num(lightness * 100, 1)}%)"
    if syntax == "oklch":
        return format_oklch(hex_color)
    raise ValueError(f"unknown color syntax: {syntax!r}")


def _num(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def swatch_keys(count: int, naming: str = "numbered") -> list[str]:
    """Keys for swatch names; the scale naming only applies to exactly 11 colors."""
    if naming == "scale" and count == len(SCALE_KEYS):
        return list(SCALE_KEYS)
    return [str(i + 1) for i in range(count)]


def _names(prefix: str, keys) -> list[str]:
    return [f"{prefix}-{key}" for key in keys]


def color_list(name: str, colors, prefix: str, syntax: str = "hex", naming: str = "numbered") -> str:
    return "".join(format_color(c, syntax) + "\n" for c in colors)


def css_variables(name: str, colors, prefix: str, syntax: str = "hex", naming: str = "numbered") -> str:
    lines = [f"/* {name} */", ":root {"]
    names = _names(prefix, swatch_keys(len(colors), naming))
    lines += [f"  --{n}: {format_color(c, syntax)};" for n, c in zip(names, colors)]
    lines.append("}")
    return "\n".join(lines) + "\n"


def tailwind_v4(name: str, colors, prefix: str, syntax: str = "hex", naming: str = "numbered") -> str:
    """Tailwind CSS v4 theme variables: utilities like ``bg-<prefix>-1`` come for free."""
    lines = [f"/* {name}: paste into your main CSS file after @import \"tailwindcss\"; */", "@theme {"]
    names = _names(prefix, swatch_keys(len(colors), naming))
    lines += [f"  --color-{n}: {format_color(c, syntax)};" for n, c in zip(names, colors)]
    lines.append("}")
    return "\n".join(lines) + "\n"


def tailwind_v3(name: str, colors, prefix: str, syntax: str = "hex", naming: str = "numbered") -> str:
    """Tailwind CSS v3 ``tailwind.config.js`` extending the color palette."""
    keys = swatch_keys(len(colors), naming)
    entries = "\n".join(f"          {k}: '{format_color(c, syntax)}'," for k, c in zip(keys, colors))
    return (
        f"/** {name} */\n"
        "/** @type {import('tailwindcss').Config} */\n"
        "module.exports = {\n"
        "  theme: {\n"
        "    extend: {\n"
        "      colors: {\n"
        f"        '{prefix}': {{\n"
        f"{entries}\n"
        "        },\n"
        "      },\n"
        "    },\n"
        "  },\n"
        "};\n"
    )


def design_tokens(name: str, colors, prefix: str, syntax: str = "hex", naming: str = "numbered") -> str:
    """W3C Design Tokens Format Module (2025.10) color tokens.

    The value is the spec's color object (sRGB components plus the optional hex
    fallback); the group carries ``$type`` so every token inherits it.
    """
    group = {"$type": "color", "$description": name}
    for key, hex_color in zip(swatch_keys(len(colors), naming), colors):
        r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
        group[key] = {
            "$value": {
                "colorSpace": "srgb",
                "components": [_round(r), _round(g), _round(b)],
                "hex": normalize_hex(hex_color).lower(),
            }
        }
    return json.dumps({prefix: group}, indent=2, ensure_ascii=False) + "\n"


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if math.isclose(rounded, 0.0) else rounded
