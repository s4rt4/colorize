"""Theme switching: palette + stylesheet + recolored icons, applied live."""

from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import QApplication

from colorize.ui.themes.icons import ICONS, svg_for
from colorize.ui.themes.qss import build_qss
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


class ThemeManager(QObject):
    """Owns the active theme. Widgets read tokens from here and re-render on ``changed``."""

    changed = pyqtSignal(str)

    def __init__(self, app: QApplication, icon_cache_dir: Path, parent=None):
        super().__init__(parent)
        self._app = app
        self._cache = Path(icon_cache_dir)
        self._name = ""
        self._bound: list[tuple[object, str]] = []
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
        icon_dir = self._write_icons(name)
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
        icon = QIcon()
        icon.addFile(str(self.icon_path(name, "-muted" if muted else "")))
        icon.addFile(str(self.icon_path(name, "-disabled")), mode=QIcon.Mode.Disabled)
        return icon

    def bind_icon(self, obj, name: str) -> None:
        """Set ``obj``'s icon now and again on every theme change (anything with ``setIcon``)."""
        obj.setIcon(self.icon(name))
        self._bound.append((obj, name))

    def _write_icons(self, name: str) -> Path:
        tokens = THEMES[name]
        folder = self._cache / name
        folder.mkdir(parents=True, exist_ok=True)
        for icon_name in ICONS:
            for suffix, token in _ICON_VARIANTS.items():
                path = folder / f"{icon_name}{suffix}.svg"
                svg = svg_for(icon_name, tokens[token])
                if not path.exists() or path.read_text(encoding="utf-8") != svg:
                    path.write_text(svg, encoding="utf-8")
        return folder
