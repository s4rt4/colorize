import pytest

from colorize.core.color import to_oklch
from colorize.core.gamut import in_srgb_gamut
from colorize.core.scale import DARKEST, LIGHTEST, SCALE_STEPS, base_step_index, tint_shade_scale


@pytest.mark.parametrize("base", ["#3D6A9E", "#E63946", "#F2C14E", "#2CA02C", "#808080", "#111111", "#FAFAFA"])
def test_scale_shape(base):
    scale = tint_shade_scale(base)
    assert [s.step for s in scale] == list(SCALE_STEPS)
    assert sum(s.is_base for s in scale) == 1
    base_step = next(s for s in scale if s.is_base)
    assert base_step.hex == base  # the base color itself, untouched
    levels = [to_oklch(s.hex)[0] for s in scale]
    assert levels == sorted(levels, reverse=True)  # light to dark
    assert len({s.hex for s in scale}) == len(scale)
    for s in scale:
        assert in_srgb_gamut(*to_oklch(s.hex))


def test_lightness_is_evenly_spaced_on_each_side():
    scale = tint_shade_scale("#3D6A9E")
    k = next(i for i, s in enumerate(scale) if s.is_base)
    upper = [s.lightness for s in scale[: k + 1]]
    lower = [s.lightness for s in scale[k:]]
    for side in (upper, lower):
        gaps = [a - b for a, b in zip(side, side[1:])]
        assert max(gaps) - min(gaps) < 1e-9
    assert scale[0].lightness == pytest.approx(LIGHTEST)
    assert scale[-1].lightness == pytest.approx(DARKEST)


def test_base_lands_on_the_nearest_step():
    assert SCALE_STEPS[base_step_index(0.97)] == 50
    assert SCALE_STEPS[base_step_index(0.62)] == 500
    assert SCALE_STEPS[base_step_index(0.20)] == 950
    assert next(s for s in tint_shade_scale("#3D6A9E") if s.is_base).step == 600  # L 0.516: nearest is 0.544


def test_hue_is_kept_and_chroma_tapers_at_the_ends():
    scale = tint_shade_scale("#3D6A9E")
    base_hue = to_oklch("#3D6A9E")[2]
    for s in scale[1:-1]:
        assert abs(to_oklch(s.hex)[2] - base_hue) < 6
    chromas = [to_oklch(s.hex)[1] for s in scale]
    assert chromas[0] < chromas[5] and chromas[-1] < chromas[5]


def test_gray_scale_stays_gray():
    for s in tint_shade_scale("#808080"):
        assert to_oklch(s.hex)[1] < 0.002


def test_custom_range_and_validation():
    scale = tint_shade_scale("#3D6A9E", lightest=0.9, darkest=0.4)
    assert scale[0].lightness == pytest.approx(0.9)
    assert scale[-1].lightness == pytest.approx(0.4)
    with pytest.raises(ValueError):
        tint_shade_scale("#3D6A9E", lightest=0.3, darkest=0.5)
