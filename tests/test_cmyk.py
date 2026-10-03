import sys
from pathlib import Path

import pytest

from colorize.core.cmyk import (
    SYSTEM_PROFILE_DIR,
    CmykProofer,
    approximate_cmyk,
    approximate_matches,
    find_cmyk_profiles,
    profile_info,
    system_profile_dirs,
)

SWOP = SYSTEM_PROFILE_DIR / "RSWOP.icm"
needs_swop = pytest.mark.skipif(not SWOP.exists(), reason="Windows SWOP profile not available")


@needs_swop
def test_finds_the_windows_swop_profile():
    profiles = find_cmyk_profiles()
    assert any(p.path.lower().endswith("rswop.icm") and "Swop" in p.description for p in profiles)
    assert all(profile_info(p.path) is not None for p in profiles)  # only CMYK ones are listed


def test_rgb_profile_is_not_a_cmyk_profile():
    srgb = SYSTEM_PROFILE_DIR / "sRGB Color Space Profile.icm"
    if srgb.exists():
        assert profile_info(srgb) is None
    assert profile_info(Path("missing.icc")) is None
    with pytest.raises(ValueError):
        CmykProofer(Path("missing.icc"))


@needs_swop
def test_press_reproduction():
    proofer = CmykProofer(SWOP)
    white, black, gray, blue, muted, gold, green = proofer.match(
        ["#FFFFFF", "#000000", "#808080", "#0000FF", "#7A8FB0", "#F2C14E", "#00FF00"]
    )
    assert white.cmyk == (0.0, 0.0, 0.0, 0.0) and white.print_hex == "#FFFFFF" and white.shift == "match"
    assert black.cmyk[3] > 60 and black.in_gamut  # mostly black ink; black point compensated
    for printable in (gray, muted, gold):
        assert printable.in_gamut, printable
    for screen_only in (blue, green):  # pure screen primaries are beyond the press
        assert screen_only.shift == "noticeable" and not screen_only.in_gamut
        assert screen_only.delta_e > 10


@needs_swop
def test_print_colors_are_stable():
    """Using what the press reproduces fixes the warning: converting it again barely moves it."""
    proofer = CmykProofer(SWOP)
    for match in proofer.match(["#0000FF", "#00FF00", "#FF00FF", "#00C853", "#FF00AA"]):
        again = proofer.match([match.print_hex])[0]
        assert again.shift != "noticeable", (match.hex, match.print_hex, again.delta_e)


@needs_swop
def test_intents_differ_for_out_of_gamut_colors():
    relative = CmykProofer(SWOP, "relative").match(["#00FF00"])[0]
    perceptual = CmykProofer(SWOP, "perceptual").match(["#00FF00"])[0]
    assert relative.cmyk != perceptual.cmyk


def test_approximation_without_profile():
    assert approximate_cmyk("#FF0000") == (0.0, 100.0, 100.0, 0.0)
    assert approximate_cmyk("#000000") == (0.0, 0.0, 0.0, 100.0)
    assert approximate_cmyk("#FFFFFF") == (0.0, 0.0, 0.0, 0.0)
    match = approximate_matches(["#808080"])[0]
    assert match.print_hex is None and match.in_gamut is None


def test_profile_folders_per_platform(tmp_path):
    assert system_profile_dirs("win32") == [SYSTEM_PROFILE_DIR]
    linux = system_profile_dirs("linux", env={}, home=tmp_path)
    assert linux == [tmp_path / ".local/share/icc", tmp_path / ".color/icc",
                     Path("/usr/local/share/color/icc"), Path("/usr/share/color/icc")]
    custom = system_profile_dirs("linux", env={"XDG_DATA_HOME": "/data", "XDG_DATA_DIRS": "/opt/share:"}, home=tmp_path)
    assert custom == [Path("/data/icc"), tmp_path / ".color/icc", Path("/opt/share/color/icc")]


@needs_swop
def test_profiles_in_package_subfolders_are_found_once(tmp_path):
    import shutil

    nested = tmp_path / "icc" / "ghostscript"
    nested.mkdir(parents=True)
    shutil.copy(SWOP, nested / "swop.icc")
    (tmp_path / "icc" / "notes.txt").write_text("not a profile")
    found = find_cmyk_profiles([tmp_path / "icc", nested], recursive=True)
    assert [Path(p.path).name for p in found] == ["swop.icc"]
    assert find_cmyk_profiles([tmp_path / "icc"], recursive=False) == []


@pytest.mark.skipif(sys.platform != "linux", reason="Linux profile packages")
def test_finds_a_cmyk_profile_from_linux_packages():
    # CI installs ghostscript, which ships default_cmyk.icc under /usr/share/color/icc
    if not any(Path(d).is_dir() for d in system_profile_dirs()):
        pytest.skip("no ICC folders on this system")
    assert find_cmyk_profiles(), "install ghostscript or colord for CMYK profiles"
