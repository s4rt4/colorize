"""Import/export formats. Named formats/ so it never shadows the stdlib io module."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from colorize.formats import colorize_json, swatch_files, text_formats


@dataclass(frozen=True)
class Exporter:
    key: str
    label: str
    suffix: str
    render: Callable  # (name, colors, prefix, syntax, naming) -> str | bytes
    uses_syntax: bool = True  # whether the color syntax option applies
    uses_names: bool = True  # whether swatch names (prefix + keys) appear in the output
    binary: bool = False


EXPORTERS = {
    e.key: e
    for e in (
        Exporter("css", "CSS Variables", ".css", text_formats.css_variables),
        Exporter("tailwind4", "Tailwind CSS v4 (@theme)", ".css", text_formats.tailwind_v4),
        Exporter("tailwind3", "Tailwind CSS v3 (config)", ".js", text_formats.tailwind_v3),
        Exporter("tokens", "Design Tokens (W3C DTCG JSON)", ".tokens.json", text_formats.design_tokens, uses_syntax=False),
        Exporter("list", "Color List", ".txt", text_formats.color_list, uses_names=False),
        Exporter(
            "ase",
            "Adobe Swatch Exchange (.ase)",
            ".ase",
            lambda name, colors, prefix, syntax, naming: swatch_files.write_ase(name, colors),
            uses_syntax=False,
            uses_names=False,
            binary=True,
        ),
        Exporter(
            "gpl",
            "GIMP / Inkscape Palette (.gpl)",
            ".gpl",
            lambda name, colors, prefix, syntax, naming: swatch_files.write_gpl(name, colors),
            uses_syntax=False,
            uses_names=False,
        ),
    )
}

IMPORT_SUFFIXES = (colorize_json.SUFFIX, ".ase", ".gpl")


def import_named_colors(path) -> tuple[str, list[tuple[str, str]]]:
    """Read (book name, [(color name, hex)]) from .ase or .gpl; unnamed colors are
    named by their hex. Used for color books (Pantone, RAL, ... exported by the user)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".ase":
        name, entries = swatch_files.read_ase_named(path.read_bytes())
    elif suffix == ".gpl":
        name, entries = swatch_files.read_gpl_named(path.read_text(encoding="utf-8", errors="replace"))
    else:
        raise swatch_files.SwatchFileError(f"color books must be .ase or .gpl: {path.name}")
    return name or path.stem, [(entry_name or hex_color, hex_color) for entry_name, hex_color in entries]


def import_palette(path) -> tuple[str, list[str]]:
    """Read a palette from .json (native), .ase or .gpl. Name falls back to the file name."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".ase":
        name, colors = swatch_files.read_ase(path.read_bytes())
    elif suffix == ".gpl":
        name, colors = swatch_files.read_gpl(path.read_text(encoding="utf-8", errors="replace"))
    elif suffix == colorize_json.SUFFIX:
        name, colors = colorize_json.loads(path.read_text(encoding="utf-8"))
    else:
        raise swatch_files.SwatchFileError(f"unsupported palette file: {path.name}")
    return name or path.stem, colors
