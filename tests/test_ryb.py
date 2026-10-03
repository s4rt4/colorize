import numpy as np
import pytest

from colorize.core.color import to_oklch
from colorize.core.harmony import harmony
from colorize.core.ryb import from_wheel, oklch_hue_to_ryb, ryb_to_oklch_hue, to_wheel


def hue_of(hex_color):
    return to_oklch(hex_color)[2]


def test_mapping_round_trips():
    angles = np.linspace(0, 359.9, 500)
    assert np.allclose(oklch_hue_to_ryb(ryb_to_oklch_hue(angles)), angles, atol=1e-6)
    hues = np.linspace(0, 359.9, 500)
    assert np.allclose(ryb_to_oklch_hue(oklch_hue_to_ryb(hues)), hues, atol=1e-6)


def test_mapping_is_monotonic_around_the_circle():
    hues = np.unwrap(np.radians(ryb_to_oklch_hue(np.linspace(0, 359, 360))))
    assert np.all(np.diff(hues) > 0)


@pytest.mark.parametrize(
    "color, complement",
    [("#FF0000", "#00FF00"), ("#FFFF00", "#800080"), ("#0000FF", "#FF7F00")],
)
def test_ryb_complements_are_the_painters_pairs(color, complement):
    lightness, chroma, hue = to_oklch(color)
    pair = harmony("complementary", lightness, chroma, hue, wheel="ryb")
    assert pair.colors[0][2] == hue  # base untouched
    assert pair.colors[1][2] == pytest.approx(hue_of(complement), abs=0.2)


def test_oklch_wheel_is_unchanged():
    result = harmony("triadic", 0.6, 0.1, 40)
    assert [round(h) for _, _, h in result.colors] == [40, 160, 280]


def test_wheel_helpers():
    assert to_wheel(123.0, "oklch") == 123.0 and from_wheel(123.0, "oklch") == 123.0
    assert to_wheel(hue_of("#FFFF00"), "ryb") == pytest.approx(120, abs=0.1)
    assert from_wheel(240, "ryb") == pytest.approx(hue_of("#0000FF"), abs=0.1)
