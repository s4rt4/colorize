# PyInstaller spec: one-folder build (faster start, fewer antivirus false positives
# than --onefile). Build with: python tools/build.py
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
WINDOWS = sys.platform == "win32"
VERSION_FILE = str(ROOT / "build" / "version_info.txt")  # written by tools/build.py (Windows)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "colorize" / "ui" / "fonts"), "colorize/ui/fonts"),
        (str(ROOT / "colorize" / "ui" / "assets"), "colorize/ui/assets"),
        (str(ROOT / "LICENSE"), "."),
    ],
    hiddenimports=["PyQt6.QtSvg"] + ([] if WINDOWS else ["PyQt6.QtDBus"]),  # D-Bus: Wayland screen portal
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "pytest",
        "pytestqt",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtMultimedia",
        "PyQt6.QtNetwork",
        "PyQt6.QtOpenGL",
        "PyQt6.QtPdf",
    ] + (["PyQt6.QtDBus"] if WINDOWS else []),  # only the Linux Wayland screen portal uses D-Bus
    noarchive=False,
)

# Drop pieces the app never uses (~40 MB): software OpenGL (widgets render with the
# raster engine), Qt PDF, Pillow's AVIF codec (not an opened format), and Qt's own
# translations (the UI is English).
UNUSED = ("opengl32sw", "qt6pdf", "qpdf.", "_avif.")  # matched without extension: .dll and .so alike


def keep(entry) -> bool:
    name = entry[0].replace("\\", "/").lower()
    return not any(part in name for part in UNUSED) and "/qt6/translations/" not in name


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Colorize",
    console=False,
    icon=str(ROOT / "colorize" / "ui" / "assets" / "colorize.ico") if WINDOWS else None,
    version=VERSION_FILE if WINDOWS else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Colorize", upx=False)
