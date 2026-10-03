"""Native palette file: UTF-8 JSON.

    {"format": "colorize.palette", "version": 1, "name": "...", "colors": [{"hex": "#RRGGBB"}]}

Colors are objects so later versions can add names/tags without breaking old files.
"""

import json

from colorize.core.color import normalize_hex

FORMAT_ID = "colorize.palette"
VERSION = 1
FILE_FILTER = "Colorize Palette (*.json)"
SUFFIX = ".json"


class PaletteFormatError(ValueError):
    pass


def dumps(name: str, colors) -> str:
    data = {
        "format": FORMAT_ID,
        "version": VERSION,
        "name": name,
        "colors": [{"hex": normalize_hex(c)} for c in colors],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def loads(text: str) -> tuple[str, list[str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PaletteFormatError(f"not valid JSON: {exc.msg} (line {exc.lineno})") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        raise PaletteFormatError("not a Colorize palette file")
    version = data.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise PaletteFormatError(f"unsupported palette version: {version!r}")
    name = data.get("name")
    entries = data.get("colors")
    if not isinstance(name, str) or not isinstance(entries, list):
        raise PaletteFormatError("palette is missing a name or colors list")
    colors = []
    for i, entry in enumerate(entries):
        try:
            colors.append(normalize_hex(entry["hex"]))
        except (TypeError, KeyError, ValueError) as exc:
            raise PaletteFormatError(f"color #{i + 1} is not a valid hex color") from exc
    return name, colors
