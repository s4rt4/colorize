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


# Linux: libraries that must come from the user's system, not from the build machine
# (as on AppImage's exclude list): graphics drivers, X11/Wayland, fontconfig, D-Bus,
# glib. Also Qt's GTK3 platform theme and the whole GTK stack it drags in: the app
# styles itself, and file dialogs still follow the desktop via the xdg portal theme.
HOST_LIBS = (
    "libgl.", "libegl", "libglx", "libgldispatch", "libopengl", "libdrm", "libgbm",
    "libx11", "libxcb", "libxau", "libxdmcp", "libxext", "libxrender", "libxi.", "libxfixes", "libxkbcommon",
    "libwayland", "libfontconfig", "libfreetype", "libdbus-1", "libsystemd", "libudev",
    "libglib-2", "libgio-2", "libgobject-2", "libgmodule-2", "libgthread-2",
    "libgtk-3", "libgdk-3", "libgdk_pixbuf", "libatk", "libatspi", "libcairo", "libpango", "libharfbuzz",
    "libepoxy", "libpixman", "libfribidi", "libthai", "libdatrie",
    "libkrb5", "libgssapi", "libk5crypto", "libcom_err", "libgcrypt", "libgpg-error",
    "libselinux", "libmount", "libblkid", "libpcre2",
)


def keep(entry) -> bool:
    name = entry[0].replace("\\", "/").lower()
    if any(part in name for part in UNUSED) or "/qt6/translations/" in name:
        return False
    if not WINDOWS:
        # Only top-level entries are copies of system libraries; wheels keep their own
        # private copies in subfolders (pillow.libs/libxcb-<hash>.so...), which stay.
        if ("/" not in name and name.startswith(HOST_LIBS)) or name.endswith("platformthemes/libqgtk3.so"):
            return False
    return True


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
    strip=not WINDOWS,  # Linux: drop debug symbols (libpython alone shrinks ~25 MB)
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Colorize", strip=not WINDOWS, upx=False)
