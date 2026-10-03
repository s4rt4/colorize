"""Build the app folder (Windows or Linux) and check it like a clean machine would.

    python tools/build.py            # build + clean-environment smoke test + archive
    python tools/build.py --no-zip

Steps:
1. PyInstaller one-folder build from packaging/colorize.spec -> dist/Colorize/
   (Linux: plus colorize.desktop, colorize.png and install.sh from packaging/linux).
2. Copy it outside the project and start it with --smoke-test in a stripped
   environment: system PATH only (no Python, no dev tools), fresh AppData (Windows) or
   HOME/XDG folders (Linux), a new profile. Anything the app silently borrowed from
   this machine fails here. Linux without a display runs Qt offscreen.
   Run 3 times: first launch (cold profile) and two warm ones; report startup times.
   A 4th run opens a Display P3 photo and an ASE with a Lab swatch, so the parts that
   load lazily (Pillow + LittleCMS, NumPy extraction, coloraide) run in the frozen app.
3. Archive: dist/Colorize-<version>-win64.zip or dist/Colorize-<version>-linux-<arch>.tar.gz
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from colorize import __version__  # noqa: E402

DIST = ROOT / "dist" / "Colorize"
WINDOWS = sys.platform == "win32"
APP_EXE = "Colorize.exe" if WINDOWS else "Colorize"
LINUX_FILES = ("colorize.desktop", "colorize.png", "install.sh")
STARTUP_BUDGET_S = 3.0

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}, 0), prodvers=({v}, 0), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Colorize'),
      StringStruct('FileDescription', 'Colorize - offline color manager'),
      StringStruct('FileVersion', '{dotted}'),
      StringStruct('InternalName', 'Colorize'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'Colorize.exe'),
      StringStruct('ProductName', 'Colorize'),
      StringStruct('ProductVersion', '{dotted}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def build() -> None:
    parts = [int(p) for p in __version__.split(".")] + [0] * 3
    (ROOT / "build").mkdir(exist_ok=True)
    if WINDOWS:
        (ROOT / "build" / "version_info.txt").write_text(
            VERSION_INFO.format(v=", ".join(str(p) for p in parts[:3]), dotted=__version__), encoding="utf-8"
        )
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
         "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
         str(ROOT / "packaging" / "colorize.spec")],
        check=True,
        cwd=ROOT,
    )
    if not WINDOWS:
        for name in LINUX_FILES:
            shutil.copy2(ROOT / "packaging" / "linux" / name, DIST / name)
        (DIST / "install.sh").chmod(0o755)


def clean_env(home: Path) -> dict:
    return clean_env_windows(home) if WINDOWS else clean_env_linux(home)


def clean_env_linux(home: Path) -> dict:
    """System PATH only and a fresh HOME/XDG tree. A desktop session (X11/Wayland) is
    passed through when there is one; otherwise Qt renders offscreen."""
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "TMPDIR": str(home / "tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    for folder in (".config", ".local/share", ".cache", "tmp"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    session = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS")
    env.update({k: os.environ[k] for k in session if k in os.environ})
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        env["QT_QPA_PLATFORM"] = "offscreen"
    return env


def clean_env_windows(home: Path) -> dict:
    windows = os.environ.get("SystemRoot", r"C:\Windows")
    env = {
        "SystemRoot": windows,
        "windir": windows,
        "PATH": f"{windows}\\System32;{windows}",
        "TEMP": str(home / "temp"),
        "TMP": str(home / "temp"),
        "APPDATA": str(home / "Roaming"),
        "LOCALAPPDATA": str(home / "Local"),
        "USERPROFILE": str(home),
    }
    for folder in ("temp", "Roaming", "Local"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    return env


def sample_files(folder: Path) -> list[Path]:
    """A P3-tagged photo and an ASE holding RGB + Lab swatches."""
    import struct

    from PIL import Image

    sys.path.insert(0, str(ROOT / "tests"))
    from icc_util import matrix_profile

    from colorize.formats.swatch_files import write_ase

    photo = folder / "phone-photo.png"
    Image.new("RGB", (64, 48), (150, 110, 80)).save(photo, icc_profile=matrix_profile("display-p3", "Display P3"))
    ase = folder / "lab-swatches.ase"
    data = bytearray(write_ase("Mixed", ["#3D6A9E"]))
    name = struct.pack(">H", 2) + "L\0".encode("utf-16-be")
    payload = name + b"LAB " + struct.pack(">fffH", 0.6, 70.0, -40.0, 2)  # vivid Lab: needs gamut mapping
    data[8:12] = struct.pack(">I", struct.unpack(">I", bytes(data[8:12]))[0] + 1)
    data += struct.pack(">HI", 1, len(payload)) + payload
    ase.write_bytes(bytes(data))
    return [photo, ase]


def smoke_test() -> list[float]:
    sandbox = Path(tempfile.mkdtemp(prefix="colorize-clean-"))
    app_dir = sandbox / "Colorize"
    shutil.copytree(DIST, app_dir)
    env = clean_env(sandbox / "home")
    profile = sandbox / "profile"
    times = []
    for run in range(3):
        start = time.perf_counter()
        proc = subprocess.run(
            [str(app_dir / APP_EXE), "--profile", str(profile), "--smoke-test"],
            env=env,
            cwd=sandbox,
            timeout=60,
        )
        wall = time.perf_counter() - start
        report = profile / "smoke-test.txt"
        if proc.returncode != 0 or not report.exists():
            log = (profile / "colorize.log").read_text(encoding="utf-8", errors="replace") if (profile / "colorize.log").exists() else ""
            raise SystemExit(f"smoke test failed (exit {proc.returncode})\n{log[-2000:]}")
        line = report.read_text(encoding="utf-8").strip()
        match = re.search(r"(\d+) ms after process start", line)
        ready = int(match.group(1)) / 1000 if match else wall
        label = "first launch" if run == 0 else "warm launch "
        print(f"  {label}: window ready {ready:.2f} s after process start (with shutdown: {wall:.2f} s)")
        report.unlink()
        times.append(ready)
    files = sample_files(sandbox)
    proc = subprocess.run(
        [str(app_dir / APP_EXE), "--profile", str(profile), "--smoke-test", *map(str, files)],
        env=env,
        cwd=sandbox,
        timeout=60,
    )
    if proc.returncode != 0 or not (profile / "smoke-test.txt").exists():
        log = (profile / "colorize.log").read_text(encoding="utf-8", errors="replace")
        raise SystemExit(f"smoke test with files failed (exit {proc.returncode})\n{log[-2000:]}")
    print("  opening a P3 photo and a Lab .ase: OK")
    shutil.rmtree(sandbox, ignore_errors=True)
    return times


def make_zip() -> Path:
    if not WINDOWS:
        machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(), platform.machine().lower())
        target = ROOT / "dist" / f"Colorize-{__version__}-linux-{machine}.tar.gz"
        with tarfile.open(target, "w:gz") as archive:  # tar keeps the executable bits
            archive.add(DIST, arcname="Colorize")
        return target
    target = ROOT / "dist" / f"Colorize-{__version__}-win64.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in DIST.rglob("*"):
            archive.write(path, Path("Colorize") / path.relative_to(DIST))
    return target


def folder_size(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1e6


def main() -> int:
    if not (WINDOWS or sys.platform.startswith("linux")):
        raise SystemExit("this build script targets Windows and Linux")
    print(f"Building Colorize {__version__} …")
    build()
    print(f"Built {DIST} ({folder_size(DIST):.0f} MB)")
    print("Clean-environment smoke test (no Python/dev tools on PATH, fresh AppData):")
    times = smoke_test()
    verdict = "OK" if max(times[1:]) < STARTUP_BUDGET_S else "OVER BUDGET"
    print(f"  warm start budget {STARTUP_BUDGET_S:.0f} s: {verdict}")
    if "--no-zip" not in sys.argv:
        archive = make_zip()
        print(f"Packaged {archive} ({archive.stat().st_size / 1e6:.0f} MB)")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
