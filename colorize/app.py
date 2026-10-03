"""Application entry point: ``python -m colorize [files...] [--profile DIR] [--smoke-test]``.

--profile DIR   keep settings, library, cache and log in DIR instead of the user's
                AppData (clean first-run testing, portable use).
--smoke-test    start, wait until the window is up, print the startup time, exit.
Files given on the command line (palettes, swatch files, images) are opened.

Only Qt and the splash screen are imported up front; the rest loads while the
splash is showing, so something appears on screen right away.
"""

import time

_STARTED = time.perf_counter()

import logging  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402
from pathlib import Path  # noqa: E402

from PyQt6.QtCore import QSettings, QStandardPaths, QTimer  # noqa: E402
from PyQt6.QtGui import QFont, QFontDatabase, QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from colorize import __version__  # noqa: E402
from colorize.ui.splash import SplashScreen  # noqa: E402

FONT_DIR = Path(__file__).parent / "ui" / "fonts"
LOGO = Path(__file__).parent / "ui" / "assets" / "logo.svg"
UI_FONT_PX = 13
FALLBACK_UI_FONT = {"win32": "Segoe UI", "darwin": "Helvetica Neue"}.get(sys.platform, "sans-serif")

log = logging.getLogger("colorize")


@dataclass(frozen=True)
class Profile:
    """Where this run keeps its data."""

    settings: QSettings
    library: Path
    cache: Path
    log: Path

    @classmethod
    def default(cls) -> "Profile":
        data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        cache = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "Colorize", "Colorize")
        return cls(settings, data / "library.sqlite", cache / "theme-icons", data / "colorize.log")

    @classmethod
    def portable(cls, folder: Path) -> "Profile":
        folder.mkdir(parents=True, exist_ok=True)
        settings = QSettings(str(folder / "settings.ini"), QSettings.Format.IniFormat)
        return cls(settings, folder / "library.sqlite", folder / "cache" / "theme-icons", folder / "colorize.log")


def ms_since_process_start() -> float | None:
    """Wall time since Windows created this process (includes the .exe bootloader and
    interpreter start, which perf_counter-based timing misses)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE  # 64-bit pseudo-handle, not an int
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    creation, exited, kernel, user, now = (wintypes.FILETIME() for _ in range(5))
    times = (creation, exited, kernel, user)
    if not kernel32.GetProcessTimes(kernel32.GetCurrentProcess(), *(ctypes.byref(t) for t in times)):
        return None
    kernel32.GetSystemTimePreciseAsFileTime(ctypes.byref(now))

    def ticks(t):
        return (t.dwHighDateTime << 32) | t.dwLowDateTime

    return (ticks(now) - ticks(creation)) / 10_000  # 100 ns units -> ms


def parse_args(argv: list[str]) -> tuple[Path | None, bool, list[str]]:
    profile, smoke, files = None, False, []
    args = iter(argv[1:])
    for arg in args:
        if arg == "--profile":
            profile = Path(next(args, "."))
        elif arg == "--smoke-test":
            smoke = True
        elif not arg.startswith("-"):
            files.append(arg)
    return profile, smoke, files


def load_ui_font(app: QApplication) -> str:
    """Use bundled Source Sans 3 (OFL); fall back to the system UI font."""
    family = FALLBACK_UI_FONT
    for path in sorted(FONT_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            family = families[0]
    font = QFont(family)
    font.setPixelSize(UI_FONT_PX)
    app.setFont(font)
    return family


def open_library(path: Path):
    from colorize.storage.library import Library, LibraryError

    try:
        return Library(path)
    except LibraryError as exc:
        log.error("library unavailable: %s", exc)
        QMessageBox.critical(None, "Colorize", f"The palette library could not be opened:\n{exc}\n\n"
                             "Colorize will use a temporary library for this session.")
        return Library(":memory:")


def set_windows_app_id() -> None:
    """Own taskbar identity on Windows, so the taskbar shows our icon, not python.exe's."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Colorize.Colorize")


def setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def install_crash_handler(log_path: Path, smoke: bool) -> None:
    """A windowed .exe has no console: log unexpected errors and show them instead of
    letting PyQt abort the process."""
    showing = False

    def hook(kind, value, tb):
        nonlocal showing
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("unhandled exception\n%s", text)
        if smoke:
            print(text, file=sys.stderr)
            QApplication.exit(1)
            return
        if showing:
            return
        showing = True
        box = QMessageBox(QMessageBox.Icon.Critical, "Colorize", f"Something went wrong: {value}")
        box.setInformativeText(f"Your documents are still open. Details were written to:\n{log_path}")
        box.setDetailedText(text)
        box.exec()
        showing = False

    sys.excepthook = hook


def exercise_lazy_features(window, app) -> None:
    """Smoke test: run the parts that load on demand (SVG mockups, ICC transforms,
    the CSS color book), which a frozen build could be missing. Errors propagate."""
    window.open_mockup()
    for key in ("print", "match"):
        dock = window.docks[key]
        dock.toggleView(True)
        dock.setAsCurrentTab()
        app.processEvents()
    window.panels["match"].current_book()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    profile_dir, smoke, files = parse_args(argv)
    set_windows_app_id()
    app = QApplication(argv)
    app.setWindowIcon(QIcon(str(LOGO)))
    app.setOrganizationName("Colorize")
    app.setApplicationName("Colorize")
    app.setApplicationVersion(__version__)

    load_ui_font(app)
    splash = SplashScreen(str(LOGO), __version__)
    splash.show()
    splash.show_message("Reading preferences…")
    profile = Profile.portable(profile_dir) if profile_dir else Profile.default()
    setup_logging(profile.log)
    install_crash_handler(profile.log, smoke)
    log.info("Colorize %s starting (Python %s)", __version__, sys.version.split()[0])

    splash.show_message("Loading color engine…")
    from colorize.ui.main_window import MainWindow
    from colorize.ui.themes import DEFAULT_THEME, ThemeManager

    splash.show_message("Applying interface theme…")
    theme = ThemeManager(app, profile.cache)
    theme.apply(profile.settings.value("ui/theme", DEFAULT_THEME, type=str))
    splash.show_message("Opening library…")
    library = open_library(profile.library)
    splash.show_message("Building workspace…")
    window = MainWindow(theme, profile.settings, library=library)
    window.show()
    splash.finish(window)
    for path in files:
        window.open_file(str(Path(path).resolve()))

    if smoke:
        def report():
            elapsed = (time.perf_counter() - _STARTED) * 1000
            since_start = ms_since_process_start()
            line = f"Colorize {__version__} ready in {elapsed:.0f} ms after interpreter start"
            if since_start is not None:
                line += f", {since_start:.0f} ms after process start"
            exercise_lazy_features(window, app)  # after timing: these load on demand
            line += "; mockup, print and match panels OK"
            log.info(line)
            # A windowed .exe has no stdout, so the build script reads this file instead.
            (profile.log.parent / "smoke-test.txt").write_text(line + "\n", encoding="utf-8")
            if sys.stdout is not None:
                print(line, flush=True)
            window.ask_save_changes = lambda doc: "discard"
            window.close()
            app.quit()

        QTimer.singleShot(0, report)

    code = app.exec()
    library.close()
    log.info("exit %s", code)
    return code
