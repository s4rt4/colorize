import re

import pytest
from PyQt6.QtGui import QPalette

from colorize.ui.themes import THEME_ORDER, THEMES
from colorize.ui.themes.icons import ICONS
from colorize.ui.themes.qss import build_qss
from colorize.ui.themes.tokens import ACCENT_KEYS


def test_three_themes_share_the_same_tokens():
    assert THEME_ORDER == ("dark", "gray", "light")
    keys = set(THEMES["dark"])
    for name in THEME_ORDER:
        assert set(THEMES[name]) == keys


@pytest.mark.parametrize("name", THEME_ORDER)
def test_chrome_grays_are_neutral(name):
    for key, value in THEMES[name].items():
        if key in ACCENT_KEYS:
            continue
        r, g, b = value[1:3], value[3:5], value[5:7]
        assert r == g == b, f"{name}.{key} = {value} is tinted"


def test_panel_brightness_increases_dark_to_light():
    levels = [int(THEMES[name]["bg_panel"][1:3], 16) for name in THEME_ORDER]
    assert levels == sorted(levels) and len(set(levels)) == 3


@pytest.mark.parametrize("name", THEME_ORDER)
def test_qss_has_no_unresolved_placeholders(name):
    qss = build_qss(THEMES[name], "C:/icons")
    assert "$" not in qss
    for icon in re.findall(r"url\(C:/icons/([\w-]+)\.svg\)", qss):
        base = re.sub(r"-(muted|disabled|on-accent)$", "", icon)
        assert base in ICONS, icon


def test_apply_writes_icons_and_sets_palette(qapp, theme):
    events = []
    theme.changed.connect(events.append)
    theme.apply("dark")
    assert events == ["dark"]
    assert theme.icon_path("swatches").exists()
    assert theme.icon_path("check", "-on-accent").exists()
    assert qapp.palette().color(QPalette.ColorRole.Window).name().upper() == THEMES["dark"]["bg_panel"]
    assert THEMES["dark"]["bg_app"].lower() in qapp.styleSheet().lower()


def test_cycle_stops_at_ends(theme):
    theme.apply("gray")
    theme.cycle(-1)
    assert theme.name == "dark"
    theme.cycle(-1)
    assert theme.name == "dark"
    theme.cycle(1)
    theme.cycle(1)
    theme.cycle(1)
    assert theme.name == "light"


def test_unknown_theme_falls_back_to_default(theme):
    theme.apply("dark")
    theme.apply("purple")
    assert theme.name == "gray"
