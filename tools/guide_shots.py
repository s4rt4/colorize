"""Screenshots of the real app for the user guide (run by tools/make_guide.py).

    python tools/guide_shots.py OUT_DIR

Uses the real platform plugin (so the system's fallback fonts draw symbols such as
the check marks) with every window flagged WA_DontShowOnScreen: nothing appears on
screen. A scale factor makes the captures sharp for print. A throwaway profile and
library are used, so the user's own settings are never touched.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_SCALE_FACTOR", "1.6")  # 2x captures on a 125% Windows display

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
from PyQt6.QtCore import QPoint, QPointF, QRect, QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from colorize.app import LOGO, load_ui_font  # noqa: E402
from PyQt6.QtGui import QColor, QIcon  # noqa: E402

from colorize.storage.library import Library  # noqa: E402
from colorize.ui.color_render import wheel_image  # noqa: E402
from colorize.ui.color_picker import ColorPickerDialog  # noqa: E402
from colorize.ui.main_window import MainWindow  # noqa: E402
from colorize.ui.preferences import PreferencesDialog  # noqa: E402
from colorize.ui.screen_sampler import ScreenOverlay  # noqa: E402
from colorize.ui.splash import SplashScreen  # noqa: E402
from colorize.ui.themes import ThemeManager  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "build" / "guide" / "shots")
OUT.mkdir(parents=True, exist_ok=True)


def sunset_photo(path: Path) -> Path:
    """A synthetic landscape so the guide ships no third-party photo."""
    w, h = 1200, 800
    y = np.linspace(0, 1, h)[:, None, None]
    sky = (1 - y) * np.array([255, 150, 95]) + y * np.array([95, 70, 150])
    img = Image.fromarray(np.broadcast_to(sky, (h, w, 3)).astype(np.uint8).copy())
    d = ImageDraw.Draw(img)
    d.ellipse((470, 320, 730, 580), fill=(255, 214, 120))
    d.rectangle((0, 560, w, h), fill=(24, 44, 74))
    d.polygon([(0, 560), (300, 370), (620, 560)], fill=(42, 64, 100))
    d.polygon([(480, 560), (900, 320), (1200, 560)], fill=(60, 82, 118))
    d.polygon([(0, 700), (1200, 640), (1200, 800), (0, 800)], fill=(34, 92, 76))
    img = img.filter(ImageFilter.GaussianBlur(2))
    noise = np.random.default_rng(1).integers(-6, 7, (h, w, 3))
    Image.fromarray(np.clip(np.asarray(img).astype(int) + noise, 0, 255).astype(np.uint8)).save(path, quality=92)
    return path


def settle(app, rounds: int = 12) -> None:
    for _ in range(rounds):
        app.processEvents()


def hidden(widget):
    """Lay out and paint as if shown, without ever appearing on screen."""
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.show()
    return widget


def snap(widget, name: str) -> None:
    widget.grab().save(str(OUT / f"{name}.png"))


def rect_in(window, widget) -> list[int]:
    top_left = widget.mapTo(window, QPoint(0, 0))
    return [top_left.x(), top_left.y(), widget.width(), widget.height()]


def main() -> None:
    app = QApplication(sys.argv)
    load_ui_font(app)
    tmp = Path(tempfile.mkdtemp(prefix="colorize-guide-"))
    theme = ThemeManager(app, tmp / "icons")
    theme.apply("gray")
    library = Library(tmp / "library.sqlite")
    library.add_palette("Sunset", ["#1B2845", "#E07A5F", "#F2CC8F", "#81B29A", "#3D405B"], tags=["hangat", "web"])
    library.add_palette("Sawah", ["#2F4A1E", "#4E6B2A", "#6E8F2E", "#A3B86C", "#D8E2DC"], tags=["alam", "foto"])
    library.add_palette("Merek 2026", ["#0B3D91", "#FC3D21", "#FFFFFF", "#111111"], tags=["merek", "web"])

    # Print assets: the logo, and color wheels on white for the theory chapters
    QIcon(str(LOGO)).pixmap(512, 512).save(str(OUT / "logo.png"))
    for wheel in ("oklch", "ryb"):
        wheel_image(420, 2.0, 0.72, QColor("#FFFFFF"), wheel).save(str(OUT / f"wheel-{wheel}.png"))

    # Splash
    splash = hidden(SplashScreen(str(LOGO), "0.2.0"))
    splash.show_message("Building workspace…")
    settle(app)
    snap(splash, "splash")
    splash.close()

    win = MainWindow(theme, QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat), library=library)
    win.ask_save_changes = lambda doc: "discard"
    win.resize(1440, 900)
    hidden(win)
    settle(app)
    doc = win.current_document()
    doc.select(2)
    win.state.set_foreground("#3D6A9E")
    settle(app)

    # Overview + regions for the annotated figure
    snap(win, "overview")
    regions = {
        "menu": rect_in(win, win.menuBar()),
        "options": rect_in(win, win.options_bar),
        "tools": rect_in(win, win.tools_bar),
        "tabs": rect_in(win, win.doc_tabs.tabBar()),
        "canvas": rect_in(win, win.doc_tabs),
        "panels": rect_in(win, win.docks["color"].dockAreaWidget()),
        "status": rect_in(win, win.statusBar()),
    }
    (OUT / "overview.json").write_text(json.dumps(regions), encoding="utf-8")
    snap(win.tools_bar, "toolbar")
    snap(win.options_bar, "optionsbar")

    # Screen sampler: its overlay over a picture of the app, cursor on the third swatch
    chip = win.current_view().grid.cell_rect(2).center()
    cursor = QPointF(win.current_view().grid.mapTo(win, chip))
    capture = win.grab()
    capture.setDevicePixelRatio(win.devicePixelRatioF())
    overlay = ScreenOverlay(None, None, capture, 3)
    overlay.resize(win.size())
    hidden(overlay)
    overlay._cursor = cursor
    overlay.update()
    settle(app)
    overlay.grab(QRect(int(cursor.x()) - 180, int(cursor.y()) - 110, 520, 320)).save(str(OUT / "screen-sampler.png"))
    overlay.close()

    # Themes
    for name in ("dark", "light"):
        theme.apply(name)
        settle(app)
        snap(win, f"theme-{name}")
    theme.apply("gray")
    settle(app)

    # Collapsed panels
    win.actions["collapse_panels"].trigger()
    settle(app)
    snap(win, "collapsed")
    win.actions["collapse_panels"].trigger()
    settle(app)

    # Panels in the Essentials workspace
    win.docks["color"].setAsCurrentTab()
    settle(app)
    snap(win.docks["color"].widget(), "panel-color")
    win.docks["swatches"].setAsCurrentTab()
    settle(app)
    snap(win.docks["swatches"].widget(), "panel-swatches")
    win.docks["history"].setAsCurrentTab()
    win.actions["add_fg"].trigger()
    doc.set_color(0, "#22436B")
    settle(app)
    snap(win.docks["history"].widget(), "panel-history")
    win.undo_action.trigger()
    win.undo_action.trigger()
    snap(win.current_view(), "canvas")

    # Harmony (perceptual and RYB)
    win.docks["harmony"].setAsCurrentTab()
    win.harmony.set_rule("triadic")
    win.harmony.edit_base(lightness=0.64, chroma=0.15, hue=250)
    settle(app)
    snap(win.docks["harmony"].widget(), "panel-harmony")
    win.harmony.set_rule("complementary")
    win.harmony.set_base_hex("#E63946")
    win.harmony.set_wheel("ryb")
    settle(app)
    snap(win.docks["harmony"].widget(), "panel-harmony-ryb")
    win.harmony.set_wheel("oklch")

    # Scale
    win.docks["scale"].setAsCurrentTab()
    win.panels["scale"].set_base("#E63946")
    settle(app)
    snap(win.docks["scale"].widget(), "panel-scale")

    # Contrast (a failing pair, with fixes) and color blindness
    win.state.set_foreground("#7A8FB0")
    win.state.set_background("#FFFFFF")
    win._apply_workspace("accessibility")
    settle(app, 20)
    snap(win.docks["contrast"].widget(), "panel-contrast")
    doc2 = win.new_document()
    doc2.add_colors(["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B"])
    win.docks["cvd"].setAsCurrentTab()
    settle(app)
    snap(win.docks["cvd"].widget(), "panel-cvd")

    # Palette workspace: gradient, export, library, print, match
    win._apply_workspace("palette")
    win.doc_tabs.setCurrentIndex(0)
    win.state.set_foreground("#0000FF")
    win.state.set_background("#FFFF00")
    win.docks["gradient"].setAsCurrentTab()
    settle(app, 20)
    snap(win.docks["gradient"].widget(), "panel-gradient")
    export = win.panels["export"]
    export.format.setCurrentIndex(export.format.findData("tailwind4"))
    export.prefix.setText("brand")
    win.docks["export"].setAsCurrentTab()
    settle(app)
    snap(win.docks["export"].widget(), "panel-export")
    win.state.set_foreground("#E8735A")
    win.docks["library"].setAsCurrentTab()
    win.panels["library"].similar.setChecked(True)
    settle(app)
    snap(win.docks["library"].widget(), "panel-library")
    win.panels["library"].similar.setChecked(False)
    doc.add_colors(["#0066FF", "#00C853"])
    win.docks["print"].setAsCurrentTab()
    settle(app, 20)
    snap(win.docks["print"].widget(), "panel-print")
    win.docks["match"].setAsCurrentTab()
    settle(app, 20)
    snap(win.docks["match"].widget(), "panel-match")
    win.undo_action.trigger()

    # Image extraction, eyedropper sampling and color blindness proof on the image
    photo = sunset_photo(tmp / "pemandangan.jpg")
    win.state.set_extract_count(6)
    win.tool_actions["extract"].trigger()
    win.open_file(str(photo))
    settle(app, 20)
    snap(win, "image-extract")
    win.state.set_cvd(kind="deutan", severity=1.0)
    win.actions["proof"].trigger()
    settle(app, 20)
    snap(win.current_tab().scroll, "image-proof")
    win.actions["proof"].trigger()

    # Mockup tab
    win.doc_tabs.setCurrentIndex(0)
    mockup = win.open_mockup()
    settle(app, 20)
    snap(win, "mockup-window")
    mockup.export_png(str(OUT / "mockup-landing.png"), scale=1.0)
    mockup.template.setCurrentIndex(mockup.template.findData("dashboard"))
    mockup.export_png(str(OUT / "mockup-dashboard.png"), scale=1.0)

    # Home screen (no documents)
    while win.doc_tabs.count():
        win.close_document(0)
    settle(app)
    snap(win, "home")

    # Dialogs
    picker = ColorPickerDialog(theme, "#3D6A9E", "Foreground Color", win)
    picker.set_lch(0.7, 0.3, 140)
    hidden(picker)
    settle(app)
    snap(picker, "picker")
    picker.close()
    prefs = hidden(PreferencesDialog(theme, win))
    settle(app)
    snap(prefs, "preferences")
    prefs.close()

    win.close()
    library.close()
    print(f"screenshots in {OUT}")


if __name__ == "__main__":
    main()
