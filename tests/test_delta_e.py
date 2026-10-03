import random

import pytest

from colorize.core.delta_e import delta_e_2000, delta_e_hex, hex_to_lab

# Sharma, Wu & Dalal (2005), Table 1: (Lab 1, Lab 2, expected ΔE00).
SHARMA = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("lab1, lab2, expected", SHARMA)
def test_ciede2000_reference_pairs(lab1, lab2, expected):
    assert delta_e_2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)
    assert delta_e_2000(lab2, lab1) == pytest.approx(expected, abs=1e-4)  # symmetric


def test_lab_and_delta_e_match_coloraide():
    from coloraide import Color

    rng = random.Random(11)
    for _ in range(200):
        a, b = ("#{:02X}{:02X}{:02X}".format(*(rng.randrange(256) for _ in range(3))) for _ in range(2))
        expected_lab = Color(a).convert("lab-d65").coords()
        assert hex_to_lab(a) == pytest.approx(expected_lab, abs=2e-3)
        expected = Color(a).convert("lab-d65").delta_e(Color(b).convert("lab-d65"), method="2000")
        assert delta_e_hex(a, b) == pytest.approx(expected, abs=5e-3)


def test_identical_colors():
    assert delta_e_hex("#3D6A9E", "#3D6A9E") == 0.0
