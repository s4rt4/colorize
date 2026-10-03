import pytest

from colorize.core.color import to_oklch
from colorize.core.contrast import contrast_ratio
from colorize.core.roles import ROLES, assign_roles

PALETTE = ["#1F3A5F", "#3D6A9E", "#7FB2E5", "#F2C14E", "#F78154", "#4D9078", "#B4436C", "#F2F2F2"]


def test_light_mode_roles():
    roles = assign_roles(PALETTE)
    c = roles.colors
    assert set(c) == set(ROLES)
    assert c["background"] == "#F2F2F2"  # lightest
    assert c["text"] == "#1F3A5F"  # darkest that reads on it
    assert contrast_ratio(c["text"], c["background"]) >= 4.5
    chromas = {h: to_oklch(h)[1] for h in PALETTE}
    assert c["primary"] == max((h for h in PALETTE if h not in ("#F2F2F2", "#1F3A5F")), key=chromas.get)
    assert len({c["primary"], c["secondary"], c["accent"]}) == 3
    assert {"background", "text", "primary", "secondary", "accent"} <= roles.from_palette
    # derived roles sit between background and text in lightness
    lightness = {r: to_oklch(c[r])[0] for r in ("background", "surface", "border", "muted", "text")}
    assert lightness["background"] >= lightness["surface"] >= lightness["border"] > lightness["muted"] > lightness["text"]


def test_dark_mode_flips_background_and_text():
    roles = assign_roles(PALETTE, dark=True)
    assert to_oklch(roles.colors["background"])[0] < 0.3
    assert contrast_ratio(roles.colors["text"], roles.colors["background"]) >= 4.5


def test_fallbacks_without_light_or_dark_colors():
    roles = assign_roles(["#E63946", "#457B9D"])
    assert roles.colors["background"] == "#FFFFFF"
    assert roles.colors["text"] == "#141414"
    assert "background" not in roles.from_palette
    empty = assign_roles([])
    assert empty.colors["background"] == "#FFFFFF" and empty.chart


def test_shuffle_rotates_brand_colors():
    first = assign_roles(PALETTE, rotation=0).colors["primary"]
    second = assign_roles(PALETTE, rotation=1).colors["primary"]
    assert first != second
    assert assign_roles(PALETTE, rotation=len(PALETTE) * 3).colors  # any rotation is valid


def test_overrides_pin_roles():
    roles = assign_roles(PALETTE, overrides={"primary": "#4d9078", "background": "#FFFFFF"})
    assert roles.colors["primary"] == "#4D9078" and roles.colors["background"] == "#FFFFFF"


def test_label_color_and_contrast_report():
    roles = assign_roles(["#FFFFFF", "#111111", "#FFE066", "#1D3557"])
    assert roles.on("primary") in ("#FFFFFF", "#141414")
    assert contrast_ratio(roles.on("primary"), roles.colors["primary"]) == pytest.approx(
        max(contrast_ratio("#FFFFFF", roles.colors["primary"]), contrast_ratio("#141414", roles.colors["primary"]))
    )
    weak = assign_roles(["#FFFFFF", "#BBBBBB"], overrides={"text": "#BBBBBB"})
    assert any(p.startswith("Text on background") for p in weak.contrast_problems())


def test_brand_colors_used_as_text_are_checked():
    roles = assign_roles(["#F2F2F2", "#1F3A5F", "#F78154"])  # orange primary on a light background
    problems = roles.contrast_problems()
    assert any(p.startswith("Primary headline on background") for p in problems)  # ~2.4:1 < 3:1
    good = assign_roles(["#FFFFFF", "#111111", "#0B5394", "#7B1FA2"])
    assert not any("Primary" in p for p in good.contrast_problems())
