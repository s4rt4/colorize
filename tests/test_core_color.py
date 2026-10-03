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
