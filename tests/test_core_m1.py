import numpy as np
import pytest
from coloraide import Color

from colorize.core.color import to_oklch
from colorize.core.gamut import MAX_SRGB_CHROMA, in_srgb_gamut, map_to_srgb, max_chroma
from colorize.core.harmony import HUE_OFFSETS, RULES, harmony, offset_of
from colorize.core.oklab import oklch_to_srgb
from colorize.formats.colorize_json import PaletteFormatError, dumps, loads


def hue_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ---------------------------------------------------------------- harmony


@pytest.mark.parametrize("rule", [r for r in RULES if r != "monochromatic"])
def test_hue_rules_keep_lightness_and_chroma(rule):
    result = harmony(rule, 0.62, 0.14, 250)
    assert result.colors[result.base_index] == (0.62, 0.14, 250)
    for lightness, chroma, _ in result.colors:
        assert (lightness, chroma) == (0.62, 0.14)


@pytest.mark.parametrize(
    "rule, expected",
    [
        ("complementary", [0, 180]),
        ("triadic", [0, 120, 240]),
        ("tetradic", [0, 90, 180, 270]),
        ("split", [0, 150, 210]),
        ("analogous", [0, 30, 60, 300, 330]),
    ],
)
def test_hue_spacing(rule, expected):
    base_hue = 40
    hues = sorted(round((h - base_hue) % 360) for _, _, h in harmony(rule, 0.6, 0.1, base_hue).colors)
    assert hues == expected


def test_complement_is_opposite_and_wraps():
    result = harmony("complementary", 0.5, 0.1, 300)
    assert result.colors[1][2] == pytest.approx(120)
    assert hue_distance(result.colors[0][2], result.colors[1][2]) == pytest.approx(180)


def test_hue_is_normalized():
    result = harmony("triadic", 0.5, 0.1, -30)
    assert all(0 <= h < 360 for _, _, h in result.colors)
    assert result.colors[result.base_index][2] == pytest.approx(330)


@pytest.mark.parametrize("base", [0.05, 0.5, 0.62, 0.99])
def test_monochromatic_steps_lightness_only(base):
    result = harmony("monochromatic", base, 0.1, 200)
    levels = [c[0] for c in result.colors]
    assert len(levels) == 5
    assert levels == sorted(levels)
    assert levels[result.base_index] == base
    assert len(set(levels)) == 5
    assert all(c[1:] == (0.1, 200) for c in result.colors)


def test_offset_of_matches_rule_table():
    assert offset_of("split", 0) == 150
    assert offset_of("monochromatic", 3) == 0
    for rule, offsets in HUE_OFFSETS.items():
        assert [offset_of(rule, i) for i in range(len(offsets))] == list(offsets)


def test_unknown_rule():
    with pytest.raises(ValueError):
        harmony("rainbow", 0.5, 0.1, 0)


# ------------------------------------------------------------------ gamut


def test_hex_colors_are_in_gamut():
    for hex_color in ("#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#3D6A9E"):
        assert in_srgb_gamut(*to_oklch(hex_color))


def test_mapping_keeps_in_gamut_colors_exact():
    mapped = map_to_srgb(*to_oklch("#3D6A9E"))
    assert mapped == map_to_srgb(*to_oklch("#3D6A9E"))
    assert mapped.hex == "#3D6A9E" and mapped.in_gamut


def test_out_of_gamut_maps_by_reducing_chroma():
    mapped = map_to_srgb(0.7, 0.3, 140)
    assert not mapped.in_gamut
    lightness, chroma, hue = to_oklch(mapped.hex)
    assert chroma < 0.3
    assert hue == pytest.approx(140, abs=3)
    assert lightness == pytest.approx(0.7, abs=0.02)


def test_max_chroma_is_the_gamut_boundary():
    limit = max_chroma(0.7, 140)
    assert in_srgb_gamut(0.7, limit * 0.98, 140)
    assert not in_srgb_gamut(0.7, limit * 1.05, 140)
    assert limit < MAX_SRGB_CHROMA


# ----------------------------------------------------- vectorized renderer


def test_numpy_renderer_matches_coloraide():
    rng = np.random.default_rng(7)
    lightness = rng.uniform(0.05, 0.95, 200)
    chroma = rng.uniform(0, 0.3, 200)
    hue = rng.uniform(0, 360, 200)
    rgb, inside = oklch_to_srgb(lightness, chroma, hue)
    for i in range(200):
        color = Color("oklch", [lightness[i], chroma[i], hue[i]])
        assert inside[i] == color.in_gamut("srgb", tolerance=1e-4) or abs(chroma[i] - max_chroma(lightness[i], hue[i])) < 1e-3
        if inside[i]:
            expected = color.convert("srgb").coords()
            assert rgb[i] == pytest.approx(expected, abs=2e-4)


# -------------------------------------------------------------- JSON file


def test_json_round_trip():
    text = dumps("Brand ✓", ["#ff0000", "0a0"])
    assert loads(text) == ("Brand ✓", ["#FF0000", "#00AA00"])


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"format": "other", "version": 1, "name": "x", "colors": []}',
        '{"format": "colorize.palette", "version": 99, "name": "x", "colors": []}',
        '{"format": "colorize.palette", "version": 1, "colors": []}',
        '{"format": "colorize.palette", "version": 1, "name": "x", "colors": [{"hex": "nope"}]}',
        '{"format": "colorize.palette", "version": 1, "name": "x", "colors": ["#fff"]}',
    ],
)
def test_json_rejects_bad_files(text):
    with pytest.raises(PaletteFormatError):
        loads(text)
