"""Application entry point: ``python -m colorize``."""

import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication

from colorize import __version__
from colorize.ui.main_window import MainWindow
from colorize.ui.themes import DEFAULT_THEME, ThemeManager

FONT_DIR = Path(__file__).parent / "ui" / "fonts"
LOGO = Path(__file__).parent / "ui" / "assets" / "logo.svg"
UI_FONT_PX = 13


def load_ui_font(app: QApplication) -> str:
    """Use bundled Source Sans 3 (OFL); fall back to Segoe UI."""
    family = "Segoe UI"
    for path in sorted(FONT_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            family = families[0]
    font = QFont(family)
    font.setPixelSize(UI_FONT_PX)
    app.setFont(font)
    return family


def create_settings() -> QSettings:
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "Colorize", "Colorize")


def icon_cache_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    return Path(base) / "theme-icons"


def set_windows_app_id() -> None:
    """Own taskbar identity on Windows, so the taskbar shows our icon, not python.exe's."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Colorize.Colorize")


def main(argv: list[str] | None = None) -> int:
    set_windows_app_id()
    app = QApplication(sys.argv if argv is None else argv)
    app.setWindowIcon(QIcon(str(LOGO)))
    app.setOrganizationName("Colorize")
    app.setApplicationName("Colorize")
    app.setApplicationVersion(__version__)
    load_ui_font(app)

    settings = create_settings()
    theme = ThemeManager(app, icon_cache_dir())
    theme.apply(settings.value("ui/theme", DEFAULT_THEME, type=str))

    window = MainWindow(theme, settings)
    window.show()
    return app.exec()
