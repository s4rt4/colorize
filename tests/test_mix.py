import pytest

from colorize.core.color import to_oklch
from colorize.core.mix import INTERPOLATIONS, css_linear_gradient, gradient, mix


@pytest.mark.parametrize("space", INTERPOLATIONS)
def test_endpoints_are_exact(space):
    assert mix("#1f3a5f", "#F2C14E", 0, space) == "#1F3A5F"
    assert mix("#1f3a5f", "#F2C14E", 1, space) == "#F2C14E"
    steps = gradient(["#1F3A5F", "#F2C14E"], 7, space)
    assert steps[0] == "#1F3A5F" and steps[-1] == "#F2C14E" and len(steps) == 7


def test_oklab_midpoint_is_perceptually_halfway():
    lightness = to_oklch(mix("#000000", "#FFFFFF", 0.5, "oklab"))[0]
    assert lightness == pytest.approx(0.5, abs=0.005)
    assert to_oklch(mix("#000000", "#FFFFFF", 0.5, "srgb"))[0] == pytest.approx(0.6, abs=0.01)  # sRGB is not


def test_oklab_avoids_the_gray_middle_of_srgb():
    oklab = to_oklch(mix("#0000FF", "#FFFF00", 0.5, "oklab"))[1]
    srgb = to_oklch(mix("#0000FF", "#FFFF00", 0.5, "srgb"))[1]
    assert srgb < 0.01  # sRGB blue + yellow = plain gray
    assert oklab > srgb


def test_oklch_takes_the_shorter_hue_path():
    red_hue, blue_hue = to_oklch("#FF0000")[2], to_oklch("#0000FF")[2]  # ~29° and ~264°
    middle = to_oklch(mix("#FF0000", "#0000FF", 0.5, "oklch"))[2]
    # the short way from 29° to 264° goes backwards through 0° (magenta), not through green
    assert middle > 300 or middle < red_hue
    assert not (90 < middle < 200)


def test_oklch_gray_end_borrows_hue():
    middle = to_oklch(mix("#808080", "#E63946", 0.5, "oklch"))
    assert abs(middle[2] - to_oklch("#E63946")[2]) < 3


def test_multi_stop_gradient_hits_every_stop():
    stops = ["#FF0000", "#00FF00", "#0000FF"]
    colors = gradient(stops, 5)
    assert colors[0] == "#FF0000" and colors[2] == "#00FF00" and colors[4] == "#0000FF"


def test_css():
    assert css_linear_gradient(["#FF0000", "#0000ff"], "oklab") == "linear-gradient(90deg in oklab, #ff0000, #0000ff)"
    assert css_linear_gradient(["#FF0000", "#0000ff"], "srgb", 45) == "linear-gradient(45deg, #ff0000, #0000ff)"


def test_validation():
    with pytest.raises(ValueError):
        gradient(["#FFFFFF"], 5)
    with pytest.raises(ValueError):
        mix("#000000", "#FFFFFF", 0.5, "hsl")
