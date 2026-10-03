"""Theme switching: palette + stylesheet + recolored icons, applied live."""

import hashlib
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QByteArray, QObject, QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

from colorize.ui.themes.icons import svg_for
from colorize.ui.themes.qss import QSS_ICON_FILES, build_qss
from colorize.ui.themes.tokens import (
    DEFAULT_THEME,
    THEME_LABELS,
    THEME_ORDER,
    THEMES,
)

__all__ = ["DEFAULT_THEME", "THEME_LABELS", "THEME_ORDER", "THEMES", "ThemeManager"]

# Suffix -> token used to color that icon variant.
_ICON_VARIANTS = {
    "": "text",
    "-muted": "text_muted",
    "-disabled": "text_disabled",
    "-on-accent": "accent_text",
}


def build_palette(tokens: dict[str, str]) -> QPalette:
    def c(key):
        return QColor(tokens[key])

    R = QPalette.ColorRole
    pal = QPalette()
    for role, key in (
        (R.Window, "bg_panel"),
        (R.WindowText, "text"),
        (R.Base, "bg_input"),
        (R.AlternateBase, "bg_header"),
        (R.ToolTipBase, "bg_header"),
        (R.ToolTipText, "text"),
        (R.PlaceholderText, "text_muted"),
        (R.Text, "text"),
        (R.Button, "bg_hover"),
        (R.ButtonText, "text"),
        (R.BrightText, "accent_text"),
        (R.Light, "bg_selected"),
        (R.Midlight, "bg_hover"),
        (R.Mid, "border_input"),
        (R.Dark, "border"),
        (R.Shadow, "border"),
        (R.Highlight, "accent"),
        (R.HighlightedText, "accent_text"),
        (R.Link, "accent"),
    ):
        pal.setColor(role, c(key))
    for role in (R.WindowText, R.Text, R.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c("text_disabled"))
    return pal


class SvgIconEngine(QIconEngine):
    """Renders an icon straight from SVG text (one per mode), sharp at any size and
    device pixel ratio, with no files involved."""

    def __init__(self, svgs: dict):
        super().__init__()
        self._svgs = svgs
        self._renderers: dict = {}

    def _renderer(self, mode) -> QSvgRenderer:
        mode = mode if mode in self._svgs else QIcon.Mode.Normal
        if mode not in self._renderers:
            self._renderers[mode] = QSvgRenderer(QByteArray(self._svgs[mode].encode()))
        return self._renderers[mode]

    def paint(self, painter, rect, mode, state):
        self._renderer(mode).render(painter, QRectF(rect))

    def scaledPixmap(self, size, mode, state, scale):
        pixmap = QPixmap(size * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(QPoint(0, 0), pixmap.size()), mode, state)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def clone(self):
        return SvgIconEngine(self._svgs)


class ThemeManager(QObject):
    """Owns the active theme. Widgets read tokens from here and re-render on ``changed``."""

    changed = pyqtSignal(str)

    def __init__(self, app: QApplication, icon_cache_dir: Path, parent=None):
        super().__init__(parent)
        self._app = app
        self._cache = Path(icon_cache_dir)
        self._name = ""
        self._bound: list[tuple[object, str]] = []
        self._icons: dict[tuple, QIcon] = {}
        app.setStyle("Fusion")

    @property
    def name(self) -> str:
        return self._name

    @property
    def tokens(self) -> dict[str, str]:
        return THEMES[self._name]

    def color(self, key: str) -> QColor:
        return QColor(self.tokens[key])

    def apply(self, name: str) -> None:
        if name not in THEMES:
            name = DEFAULT_THEME
        if name == self._name:
            return
        self._name = name
        self._icons.clear()
        icon_dir = self._write_stylesheet_icons(name)
        self._app.setPalette(build_palette(self.tokens))
        self._app.setStyleSheet(build_qss(self.tokens, icon_dir.as_posix()))
        hints = self._app.styleHints()
        if hasattr(hints, "setColorScheme"):  # Qt 6.8+: also darkens the Windows title bar
            scheme = Qt.ColorScheme.Light if name == "light" else Qt.ColorScheme.Dark
            hints.setColorScheme(scheme)
        for obj, icon_name in list(self._bound):
            if sip.isdeleted(obj):
                self._bound.remove((obj, icon_name))
            else:
                obj.setIcon(self.icon(icon_name))
        self.changed.emit(name)

    def cycle(self, step: int) -> None:
        """Move toward darker (step < 0) or lighter (step > 0), stopping at the ends."""
        index = THEME_ORDER.index(self._name) + step
        self.apply(THEME_ORDER[max(0, min(index, len(THEME_ORDER) - 1))])

    def icon_path(self, name: str, variant: str = "") -> Path:
        return self._cache / self._name / f"{name}{variant}.svg"

    def icon(self, name: str, muted: bool = False) -> QIcon:
        key = (name, muted)
        if key not in self._icons:
            tokens = self.tokens
            engine = SvgIconEngine(
                {
                    QIcon.Mode.Normal: svg_for(name, tokens["text_muted" if muted else "text"]),
                    QIcon.Mode.Active: svg_for(name, tokens["text_muted" if muted else "text"]),
                    QIcon.Mode.Selected: svg_for(name, tokens["accent_text"]),
                    QIcon.Mode.Disabled: svg_for(name, tokens["text_disabled"]),
                }
            )
            self._icons[key] = QIcon(engine)
        return self._icons[key]

    def bind_icon(self, obj, name: str) -> None:
        """Set ``obj``'s icon now and again on every theme change (anything with ``setIcon``)."""
        obj.setIcon(self.icon(name))
        self._bound.append((obj, name))

    def _write_stylesheet_icons(self, name: str) -> Path:
        """Qt stylesheets can only reference image files, so the few icons the QSS uses
        are written to the cache. A stamp of their content skips all file I/O when the
        cache is current (every file touch costs milliseconds on Windows)."""
        tokens = THEMES[name]
        folder = self._cache / name
        files = {}
        for file_name in sorted(QSS_ICON_FILES):
            icon_name, suffix = _split_variant(file_name)
            files[file_name] = svg_for(icon_name, tokens[_ICON_VARIANTS[suffix]])
        digest = hashlib.sha1("".join(files.values()).encode()).hexdigest()
        stamp = folder / ".stamp"
        try:
            if stamp.read_text(encoding="utf-8") == digest:
                return folder
        except OSError:
            pass
        folder.mkdir(parents=True, exist_ok=True)
        for file_name, svg in files.items():
            (folder / f"{file_name}.svg").write_text(svg, encoding="utf-8")
        stamp.write_text(digest, encoding="utf-8")
        return folder


def _split_variant(file_name: str) -> tuple[str, str]:
    for suffix in ("-on-accent", "-disabled", "-muted"):
        if file_name.endswith(suffix):
            return file_name[: -len(suffix)], suffix
    return file_name, ""
