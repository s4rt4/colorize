"""CMYK print preview through an ICC profile (LittleCMS, via Pillow's ImageCms).

For each color: its CMYK values for the profile's printing condition, the color the
press reproduces, and the CIEDE2000 difference between the two.

"Reproduces" is sRGB -> CMYK -> sRGB, relative colorimetric with black point
compensation both ways: what Photoshop's Convert to Profile gives, without simulating
paper or black ink. Colors the press can't reach come back clipped to its gamut, and
those clipped colors are stable (converting them again moves them by only ~1-3 dE,
the profile's own precision), so they are what to use instead. LittleCMS's separate
gamut check was tried and dropped: with coarse profiles it disagrees with the
conversion itself, flagging colors that convert unchanged and passing ones that shift.

No profile ships with Colorize (profile licenses vary). Windows includes a SWOP
profile; on Linux, CMYK profiles come from packages (colord, ghostscript, icc-profiles)
in the XDG icc folders. Others (e.g. Coated FOGRA39 from ECI) can be loaded by the
user. Without a profile only a device-independent *approximation* of CMYK is possible.
"""

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageCms

from colorize.core.color import hex_to_rgb, normalize_hex
from colorize.core.delta_e import delta_e_hex

# CIEDE2000 between screen and print: up to MATCH reads as the same color, above
# NOTICEABLE the shift is obvious side by side (common press tolerances sit at 2-5).
MATCH_DELTA_E = 2.0
NOTICEABLE_DELTA_E = 5.0

INTENTS = {
    "relative": ImageCms.Intent.RELATIVE_COLORIMETRIC,
    "perceptual": ImageCms.Intent.PERCEPTUAL,
}
INTENT_LABELS = {"relative": "Relative Colorimetric", "perceptual": "Perceptual"}
SYSTEM_PROFILE_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "spool" / "drivers" / "color"


def system_profile_dirs(platform: str = sys.platform, env=os.environ, home: Path | None = None) -> list[Path]:
    """Where the OS keeps ICC profiles. Linux follows the freedesktop ICC spec
    ($XDG_DATA_HOME/icc, <each XDG_DATA_DIRS>/color/icc, ~/.color/icc), whose
    profiles sit in per-package subfolders, so those are searched recursively."""
    home = home or Path.home()
    if platform == "win32":
        return [SYSTEM_PROFILE_DIR]
    if platform == "darwin":
        return [Path("/Library/ColorSync/Profiles"), home / "Library" / "ColorSync" / "Profiles",
                Path("/System/Library/ColorSync/Profiles")]
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    data_dirs = [Path(d) for d in (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    folders = [data_home / "icc", home / ".color" / "icc"] + [d / "color" / "icc" for d in data_dirs]
    return list(dict.fromkeys(folders))

_SRGB = ImageCms.createProfile("sRGB")


@dataclass(frozen=True)
class CmykProfileInfo:
    path: str
    description: str


@dataclass(frozen=True)
class PrintMatch:
    hex: str
    cmyk: tuple[float, float, float, float]  # percentages 0-100
    print_hex: str | None  # what the press reproduces; None for the profile-less approximation
    delta_e: float | None

    @property
    def shift(self) -> str | None:
        """'match', 'slight' or 'noticeable': how different it will look printed."""
        if self.delta_e is None:
            return None
        if self.delta_e <= MATCH_DELTA_E:
            return "match"
        return "slight" if self.delta_e <= NOTICEABLE_DELTA_E else "noticeable"

    @property
    def in_gamut(self) -> bool | None:
        """Reproduced within NOTICEABLE_DELTA_E; None when unknown (no profile)."""
        return None if self.shift is None else self.shift != "noticeable"


def profile_info(path) -> CmykProfileInfo | None:
    """Description of a CMYK ICC profile, or None if it isn't a readable CMYK profile."""
    try:
        profile = ImageCms.getOpenProfile(str(path))
    except (OSError, ImageCms.PyCMSError):
        return None
    if profile.profile.xcolor_space.strip() != "CMYK":
        return None
    description = ImageCms.getProfileDescription(profile).strip() or Path(path).stem
    return CmykProfileInfo(str(path), description)


def find_cmyk_profiles(folders=None, recursive: bool | None = None) -> list[CmykProfileInfo]:
    """CMYK profiles in the system folders (or ``folders``), each file listed once."""
    if folders is None:
        folders = system_profile_dirs()
    if recursive is None:
        recursive = sys.platform != "win32"
    found, seen = [], set()
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        candidates = folder.rglob("*") if recursive else folder.iterdir()
        for path in sorted(candidates):
            if path.suffix.lower() not in (".icc", ".icm") or not path.is_file():
                continue
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            info = profile_info(path)
            if info is not None:
                found.append(info)
    return found


class CmykProofer:
    def __init__(self, profile_path, intent: str = "relative"):
        info = profile_info(profile_path)
        if info is None:
            raise ValueError(f"not a CMYK ICC profile: {profile_path}")
        self.info = info
        profile = ImageCms.getOpenProfile(str(profile_path))
        bpc = ImageCms.Flags.BLACKPOINTCOMPENSATION
        self._to_cmyk = ImageCms.buildTransform(_SRGB, profile, "RGB", "CMYK", INTENTS[intent], flags=bpc)
        self._to_rgb = ImageCms.buildTransform(
            profile, _SRGB, "CMYK", "RGB", ImageCms.Intent.RELATIVE_COLORIMETRIC, flags=bpc
        )

    def match(self, colors) -> list[PrintMatch]:
        colors = [normalize_hex(c) for c in colors]
        if not colors:
            return []
        image = Image.new("RGB", (len(colors), 1))
        image.putdata([hex_to_rgb(c) for c in colors])
        cmyk = ImageCms.applyTransform(image, self._to_cmyk)
        back = ImageCms.applyTransform(cmyk, self._to_rgb)
        results = []
        for hex_color, ink, rgb in zip(colors, cmyk.get_flattened_data(), back.get_flattened_data()):
            print_hex = "#{:02X}{:02X}{:02X}".format(*rgb)
            results.append(
                PrintMatch(hex_color, tuple(round(v * 100 / 255, 1) for v in ink), print_hex, delta_e_hex(hex_color, print_hex))
            )
        return results


@lru_cache(maxsize=4)
def cached_proofer(profile_path: str, intent: str) -> CmykProofer:
    """Reuse the LittleCMS transforms for the same profile and intent."""
    return CmykProofer(profile_path, intent)


def approximate_cmyk(hex_color: str) -> tuple[float, float, float, float]:
    """Naive device CMYK (no profile): only a rough indication, not print values."""
    r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
    k = 1 - max(r, g, b)
    if k >= 1:
        return 0.0, 0.0, 0.0, 100.0
    c, m, y = ((1 - v - k) / (1 - k) for v in (r, g, b))
    return tuple(round(v * 100, 1) for v in (c, m, y, k))


def approximate_matches(colors) -> list[PrintMatch]:
    return [PrintMatch(normalize_hex(c), approximate_cmyk(c), None, None) for c in colors]
