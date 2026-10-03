import pytest

from colorize.core.color import format_oklch, hex_to_rgb, normalize_hex, rgb_to_hex, to_oklch


@pytest.mark.parametrize(
    "raw, expected",
    [("#ff8800", "#FF8800"), ("ff8800", "#FF8800"), ("#f80", "#FF8800"), ("  abc ", "#AABBCC")],
)
def test_normalize_hex(raw, expected):
    assert normalize_hex(raw) == expected


@pytest.mark.parametrize("raw", ["", "#12", "#12345", "#GGGGGG", "red", "#1234567"])
def test_normalize_hex_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_hex(raw)


def test_rgb_round_trip():
    assert hex_to_rgb("#0A80FF") == (10, 128, 255)
    assert rgb_to_hex(10, 128, 255) == "#0A80FF"
    with pytest.raises(ValueError):
        rgb_to_hex(256, 0, 0)


def test_oklch_reference_values():
    # Reference: CSS Color 4 / Björn Ottosson's OKLab for sRGB red.
    lightness, chroma, hue = to_oklch("#FF0000")
    assert lightness == pytest.approx(0.628, abs=1e-3)
    assert chroma == pytest.approx(0.2577, abs=1e-3)
    assert hue == pytest.approx(29.23, abs=0.05)


def test_oklch_achromatic_hue_is_zero():
    lightness, chroma, hue = to_oklch("#FFFFFF")
    assert lightness == pytest.approx(1.0, abs=1e-4)
    assert chroma == pytest.approx(0.0, abs=1e-4)
    assert hue == 0.0
    assert format_oklch("#FFFFFF").startswith("oklch(100.0% 0.000")


def test_own_oklab_math_matches_coloraide():
    """core.color avoids importing coloraide at startup; it must agree with it."""
    import random

    from coloraide import Color

    rng = random.Random(4)
    for _ in range(300):
        hex_color = "#{:02X}{:02X}{:02X}".format(*(rng.randrange(256) for _ in range(3)))
        ours = to_oklch(hex_color)
        lightness, chroma, hue = Color(hex_color).convert("oklch").coords(nans=False)
        assert ours[0] == pytest.approx(lightness, abs=1e-6)
        assert ours[1] == pytest.approx(chroma, abs=1e-6)
        if chroma > 1e-3:
            assert ours[2] == pytest.approx(hue, abs=1e-3)


def test_gamut_check_and_mapping_match_coloraide():
    import random

    from coloraide import Color

    from colorize.core.gamut import in_srgb_gamut, map_to_srgb

    rng = random.Random(9)
    for _ in range(400):
        lch = (rng.uniform(0, 1), rng.uniform(0, 0.35), rng.uniform(0, 360))
        reference = Color("oklch", list(lch))
        inside = reference.in_gamut("srgb")
        assert in_srgb_gamut(*lch) == inside
        expected = reference.clone().fit("srgb", method="oklch-chroma").convert("srgb").to_string(hex=True).upper()
        assert map_to_srgb(*lch).hex == expected


def test_startup_path_does_not_import_coloraide():
    import subprocess
    import sys

    code = (
        "import sys; import colorize.ui.main_window; "
        "print('coloraide' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
