import numpy as np
import pytest

from colorize.core.color import to_oklch
from colorize.core.contrast import (
    apca_contrast,
    apca_guidance,
    contrast_ratio,
    format_ratio,
    passes,
    suggest_text_colors,
)
from colorize.core.cvd import CVD_TYPES, MACHADO, cvd_matrix, cvd_name, simulate_hex, simulate_rgb8

# ------------------------------------------------------------------ WCAG 2.x


@pytest.mark.parametrize(
    "text, background, expected",
    [
        # Values as shown by the WebAIM Contrast Checker (webaim.org/resources/contrastchecker).
        ("#000000", "#FFFFFF", "21.00:1"),
        ("#777777", "#FFFFFF", "4.47:1"),
        ("#767676", "#FFFFFF", "4.54:1"),
        ("#0000FF", "#FFFFFF", "8.59:1"),
        ("#FF0000", "#FFFFFF", "3.99:1"),
        ("#008000", "#FFFFFF", "5.13:1"),  # 5.1375, truncated like #777 -> 4.47
        ("#FFFFFF", "#FFFFFF", "1.00:1"),
    ],
)
def test_wcag_matches_webaim(text, background, expected):
    assert format_ratio(contrast_ratio(text, background)) == expected
    assert format_ratio(contrast_ratio(background, text)) == expected  # symmetric


def test_ratio_display_never_rounds_up_into_a_pass():
    ratio = contrast_ratio("#777777", "#FFFFFF")  # 4.478...
    assert ratio < 4.5 and format_ratio(ratio) != "4.50:1"
    assert not passes("wcag", "aa", "#777777", "#FFFFFF")
    assert passes("wcag", "aa", "#767676", "#FFFFFF")


# ---------------------------------------------------------------------- APCA


@pytest.mark.parametrize(
    "text, background, expected",
    [
        # Reference values from the apca-w3 package (0.0.98G-4g) test suite.
        ("#888888", "#FFFFFF", 63.056469930209424),
        ("#FFFFFF", "#888888", -68.54146436644962),
        ("#000000", "#AAAAAA", 58.146262578561334),
        ("#AAAAAA", "#000000", -56.24113336839742),
        ("#112233", "#DDEEFF", 91.66830811481631),
        ("#DDEEFF", "#112233", -93.06770049484275),
        ("#112233", "#444444", 8.32326136957393),
        ("#444444", "#112233", -7.526878460278154),
    ],
)
def test_apca_matches_reference(text, background, expected):
    assert apca_contrast(text, background) == pytest.approx(expected, abs=1e-6)


def test_apca_guidance_levels():
    assert apca_guidance(91) == "Preferred body text OK"
    assert apca_guidance(-63) == "Content text OK"
    assert apca_guidance(10) == "Too low for text"


# --------------------------------------------------------------- suggestions


@pytest.mark.parametrize("method, target", [("wcag", "aa"), ("wcag", "aaa"), ("apca", "lc75")])
def test_suggestions_pass_and_keep_hue(method, target):
    text, background = "#7A8FB0", "#FFFFFF"
    assert not passes(method, target, text, background)
    suggestions = suggest_text_colors(method, target, text, background)
    assert suggestions
    for s in suggestions:
        assert passes(method, target, s.hex, background)
        assert abs(to_oklch(s.hex)[2] - to_oklch(text)[2]) < 4  # same hue family
    darker = next(s for s in suggestions if s.direction == "darker")
    assert darker.lightness_change < 0
    # Minimal: a slightly smaller change fails.
    from colorize.core.gamut import map_to_srgb

    lightness, chroma, hue = to_oklch(text)
    almost = map_to_srgb(lightness + darker.lightness_change * 0.95, chroma, hue).hex
    assert not passes(method, target, almost, background)


def test_no_suggestions_when_already_passing():
    assert suggest_text_colors("wcag", "aa", "#000000", "#FFFFFF") == []


def test_both_directions_on_mid_gray_background():
    suggestions = suggest_text_colors("wcag", "aa_large", "#808080", "#7F7F7F")
    assert {s.direction for s in suggestions} == {"darker", "lighter"}


# ----------------------------------------------------------------------- CVD


def test_machado_rows_preserve_white():
    for kind, table in MACHADO.items():
        assert table.shape == (11, 3, 3)
        assert np.allclose(table.sum(axis=2), 1.0, atol=2e-3), kind


@pytest.mark.parametrize(
    "kind, severity, row, expected",
    [
        # Spot values from Machado et al. 2009, Table 1.
        ("protan", 1.0, 0, [0.152286, 1.052583, -0.204868]),
        ("deutan", 1.0, 1, [0.280085, 0.672501, 0.047413]),
        ("tritan", 1.0, 2, [0.004733, 0.691367, 0.303900]),
        ("protan", 0.6, 2, [-0.007442, -0.022190, 1.029632]),
        ("tritan", 0.3, 0, [0.905871, 0.127791, -0.033662]),
    ],
)
def test_machado_table_values(kind, severity, row, expected):
    assert cvd_matrix(kind, severity)[row] == pytest.approx(expected, abs=1e-6)


def test_severity_interpolates_between_rows():
    halfway = cvd_matrix("deutan", 0.55)
    assert halfway == pytest.approx((MACHADO["deutan"][5] + MACHADO["deutan"][6]) / 2)
    assert np.allclose(cvd_matrix("protan", 0.0), np.eye(3))


def test_simulation_preserves_neutrals_and_merges_red_green():
    for kind in CVD_TYPES:
        assert simulate_hex("#FFFFFF", kind, 1.0) == "#FFFFFF"
        assert simulate_hex("#000000", kind, 1.0) == "#000000"
    assert simulate_hex("#808080", "achroma", 1.0) == "#808080"
    red = to_oklch(simulate_hex("#D62728", "deutan", 1.0))
    green = to_oklch(simulate_hex("#2CA02C", "deutan", 1.0))
    assert abs(red[2] - green[2]) < 25  # deuteranopes see both as the same yellow-brown hue
    assert to_oklch(simulate_hex("#3366FF", "achroma", 1.0))[1] < 0.002


def test_simulation_is_vectorized_and_matches_scalar():
    rgb = np.random.default_rng(2).integers(0, 256, (40, 3), dtype=np.uint8)
    out = simulate_rgb8(rgb, "tritan", 0.7)
    for pixel, simulated in zip(rgb, out):
        assert "#{:02X}{:02X}{:02X}".format(*simulated) == simulate_hex("#{:02X}{:02X}{:02X}".format(*pixel), "tritan", 0.7)


def test_names():
    assert cvd_name("deutan", 1.0) == "Deuteranopia"
    assert cvd_name("protan", 0.6) == "Protanomaly 60%"
    assert cvd_name("achroma", 0.3) == "Achromatopsia"


@pytest.mark.parametrize(
    "a, b, kind, confusable",
    [
        ("#D62728", "#2CA02C", "deutan", True),  # D3 category10 red/green
        ("#8B0000", "#006400", "deutan", True),
        ("#FF6666", "#66CC66", "deutan", True),
        ("#D62728", "#2CA02C", "protan", False),  # protans still see a large lightness step
        ("#CC0000", "#669900", "deutan", False),
        ("#1F77B4", "#FF7F0E", "deutan", False),  # blue/orange: the classic safe pair
        ("#777777", "#787878", "deutan", False),  # already alike for everyone: not a CVD issue
    ],
)
def test_confusable_pairs(a, b, kind, confusable):
    from colorize.core.cvd import confusable_pairs

    assert (confusable_pairs([a, b], kind) == [(0, 1)]) is confusable
