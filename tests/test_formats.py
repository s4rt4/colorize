import json
import re
import struct
from pathlib import Path

import pytest

from colorize.formats import EXPORTERS, import_palette
from colorize.formats.swatch_files import SwatchFileError, read_ase, read_gpl, write_ase, write_gpl
from colorize.formats.text_formats import (
    css_variables,
    design_tokens,
    format_color,
    slugify,
    tailwind_v3,
    tailwind_v4,
)

COLORS = ["#1F3A5F", "#F2C14E", "#000000", "#FFFFFF"]
INKSCAPE_PALETTES = Path(r"C:\Program Files\Inkscape\share\inkscape\palettes")


@pytest.mark.parametrize(
    "syntax, expected",
    [
        ("hex", "#1f3a5f"),
        ("rgb", "rgb(31 58 95)"),
        ("hsl", "hsl(214.7 50.8% 24.7%)"),
        ("oklch", "oklch(34.7% 0.073 256.7)"),
    ],
)
def test_color_syntax(syntax, expected):
    assert format_color("#1F3A5F", syntax) == expected


def test_hsl_of_gray_has_no_nan():
    assert format_color("#808080", "hsl") == "hsl(0 0% 50.2%)"


@pytest.mark.parametrize(
    "name, expected", [("Brand Colors", "brand-colors"), ("Untitled-1", "untitled-1"), ("2026 Q4", "c-2026-q4"), ("✓", "color")]
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_css_variables():
    css = css_variables("Brand", COLORS, "brand")
    assert ":root {" in css
    assert "  --brand-1: #1f3a5f;" in css
    assert "  --brand-4: #ffffff;" in css
    assert css.count("{") == css.count("}")


def test_tailwind_v4_uses_theme_color_namespace():
    css = tailwind_v4("Brand", COLORS, "brand", "oklch")
    assert css.splitlines()[1] == "@theme {"
    assert re.search(r"--color-brand-2: oklch\([\d.]+% [\d.]+ [\d.]+\);", css)


def test_tailwind_v3_is_a_config_module():
    js = tailwind_v3("Brand", COLORS, "brand")
    assert "module.exports = {" in js
    assert "'brand': {" in js and "1: '#1f3a5f'," in js
    assert js.count("{") == js.count("}")


def test_design_tokens_follow_dtcg_color_object():
    data = json.loads(design_tokens("Brand", COLORS, "brand"))
    group = data["brand"]
    assert group["$type"] == "color"
    token = group["1"]["$value"]
    assert token["colorSpace"] == "srgb"
    assert token["hex"] == "#1f3a5f"
    assert token["components"] == [round(31 / 255, 4), round(58 / 255, 4), round(95 / 255, 4)]
    assert group["3"]["$value"]["components"] == [0.0, 0.0, 0.0]
    assert "$type" not in group["2"]  # tokens inherit $type from the group


# -------------------------------------------------------------------- ASE


def test_ase_round_trip():
    data = write_ase("Brand ✓", COLORS)
    assert data[:4] == b"ASEF"
    assert struct.unpack(">HHI", data[4:12]) == (1, 0, len(COLORS) + 2)  # group start/end + colors
    assert read_ase(data) == ("Brand ✓", COLORS)


def test_ase_layout_matches_spec():
    data = write_ase("P", ["#FF0000"])
    # group start: type, length, name length 2 (P + NUL), "P\0" UTF-16BE
    assert data[12:24] == struct.pack(">HIH", 0xC001, 6, 2) + "P\0".encode("utf-16-be")
    color = data[24:]
    kind, length = struct.unpack(">HI", color[:6])
    assert kind == 0x0001
    body = color[6 : 6 + length]
    (units,) = struct.unpack(">H", body[:2])
    assert body[2 : 2 + units * 2].decode("utf-16-be") == "#FF0000\0"
    rest = body[2 + units * 2 :]
    assert rest[:4] == b"RGB "
    assert struct.unpack(">fffH", rest[4:]) == (1.0, 0.0, 0.0, 2)
    assert color[6 + length :] == struct.pack(">HI", 0xC002, 0)


def test_ase_reads_other_color_models():
    def entry(model, values):
        payload = struct.pack(">H", 2) + "x\0".encode("utf-16-be") + model + struct.pack(f">{len(values)}fH", *values, 2)
        return struct.pack(">HI", 1, len(payload)) + payload

    blocks = [entry(b"Gray", (0.5,)), entry(b"CMYK", (0, 0, 0, 1)), entry(b"LAB ", (1.0, 0, 0))]
    data = b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks)) + b"".join(blocks)
    name, colors = read_ase(data)
    assert name == ""
    assert colors == ["#808080", "#000000", "#FFFFFF"]


@pytest.mark.parametrize("data", [b"", b"NOPE", b"ASEF" + struct.pack(">HHI", 1, 0, 3)])
def test_ase_rejects_bad_files(data):
    with pytest.raises(SwatchFileError):
        read_ase(data)


# -------------------------------------------------------------------- GPL


def test_gpl_round_trip_and_layout():
    text = write_gpl("Brand", COLORS)
    lines = text.splitlines()
    assert lines[:4] == ["GIMP Palette", "Name: Brand", "Columns: 8", "#"]
    assert lines[4] == " 31  58  95\t#1F3A5F"
    assert read_gpl(text) == ("Brand", COLORS)


@pytest.mark.skipif(not INKSCAPE_PALETTES.exists(), reason="Inkscape not installed")
def test_reads_every_palette_shipped_with_inkscape():
    files = sorted(INKSCAPE_PALETTES.glob("*.gpl"))
    assert files
    for path in files:
        name, colors = read_gpl(path.read_text(encoding="utf-8", errors="replace"))
        assert colors, path.name


def test_gpl_rejects_other_text():
    with pytest.raises(SwatchFileError):
        read_gpl("hello")
    with pytest.raises(SwatchFileError):
        read_gpl("GIMP Palette\nnot numbers here\n")


# ------------------------------------------------------------------ registry


def test_every_exporter_renders(tmp_path):
    for key, exporter in EXPORTERS.items():
        out = exporter.render("Brand", COLORS, "brand", "hex")
        assert isinstance(out, bytes if exporter.binary else str), key
        assert out


@pytest.mark.parametrize("suffix", [".ase", ".gpl", ".json"])
def test_import_palette_by_suffix(tmp_path, suffix):
    from colorize.formats import colorize_json

    path = tmp_path / f"saved{suffix}"
    if suffix == ".ase":
        path.write_bytes(write_ase("Brand", COLORS))
    elif suffix == ".gpl":
        path.write_text(write_gpl("Brand", COLORS), encoding="utf-8")
    else:
        path.write_text(colorize_json.dumps("Brand", COLORS), encoding="utf-8")
    assert import_palette(path) == ("Brand", COLORS)


def test_import_falls_back_to_file_name(tmp_path):
    path = tmp_path / "Ocean Mood.gpl"
    path.write_text("GIMP Palette\n0 0 255\n", encoding="utf-8")
    assert import_palette(path) == ("Ocean Mood", ["#0000FF"])
