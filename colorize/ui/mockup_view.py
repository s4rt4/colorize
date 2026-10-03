"""Mockup tab: the palette applied to a sample UI, live while the palette is edited."""

from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from colorize.core.roles import ROLE_LABELS, ROLES, assign_roles
from colorize.ui.color_render import paint_swatch
from colorize.ui.mockup_templates import TEMPLATES, render_svg
from colorize.ui.navigation import CanvasNavigator, tool_cursor

ZOOM_STEPS = (0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.5, 2.0)
MOCKUP_SIZE = QSize(1200, 800)


def _chip_icon(color: str, border, size: int = 14) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    paint_swatch(p, pixmap.rect(), color, border)
    p.end()
    return pixmap


class _MockupCanvas(QWidget):
    def __init__(self, view):
        super().__init__()
        self._view = view

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._view.theme.color("bg_app"))
        self._view.renderer.render(p, self._view.mockup_rect())


class MockupView(QWidget):
    zoomChanged = pyqtSignal(float)

    def __init__(self, document, state, theme, parent=None):
        super().__init__(parent)
        self.document = document
        self.theme = theme
        self._state = state
        self._zoom = 1.0
        self._fitted = False
        self.rotation = 0
        self.overrides: dict[str, str] = {}
        self.roles = None
        self.svg = ""
        self.renderer = QSvgRenderer(self)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("canvas")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas = _MockupCanvas(self)
        self.scroll.setWidget(self.canvas)
        self.scroll.viewport().installEventFilter(self)
        self._navigator = CanvasNavigator(self.scroll, self.canvas, state, self.zoom_in, self.zoom_out)

        self.template = QComboBox()
        for key, (label, _) in TEMPLATES.items():
            self.template.addItem(label, key)
        self.dark = QCheckBox("Dark")
        self.dark.setToolTip("Use the darkest color as the background")
        self.shuffle = QPushButton("Shuffle")
        self.shuffle.setToolTip("Try the palette's colors in other brand roles")
        self.shuffle.clicked.connect(self._shuffle)
        self.export_svg_button = QPushButton("Export SVG…")
        self.export_svg_button.clicked.connect(lambda: self.export_svg())
        self.export_png_button = QPushButton("Export PNG…")
        self.export_png_button.clicked.connect(lambda: self.export_png())

        self.role_buttons: dict[str, QToolButton] = {}
        roles_row = QHBoxLayout()
        roles_row.setSpacing(4)
        for role in ROLES:
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(QMenu(button))
            button.menu().aboutToShow.connect(lambda r=role: self._fill_role_menu(r))
            self.role_buttons[role] = button
            roles_row.addWidget(button)
        roles_row.addStretch(1)
        self.problems = QLabel()
        self.problems.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Template"))
        controls.addWidget(self.template)
        controls.addWidget(self.dark)
        controls.addWidget(self.shuffle)
        controls.addStretch(1)
        controls.addWidget(self.export_svg_button)
        controls.addWidget(self.export_png_button)
        footer = QWidget()
        footer.setObjectName("panelFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(6)
        footer_layout.addLayout(controls)
        footer_layout.addLayout(roles_row)
        footer_layout.addWidget(self.problems)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(footer)

        self.template.currentIndexChanged.connect(self.rebuild)
        self.dark.toggled.connect(self._dark_toggled)
        document.palette.changed.connect(self.rebuild)
        document.palette.renamed.connect(self.rebuild)
        theme.changed.connect(self._on_theme_changed)
        state.toolChanged.connect(self._update_cursor)
        self._update_cursor()
        self._update_canvas_size()
        self.rebuild()

    # ----- content -----

    @property
    def title(self) -> str:
        return f"Mockup – {self.document.palette.name}"

    def rebuild(self, *_args) -> None:
        palette = self.document.palette
        self.roles = assign_roles(palette.colors, self.dark.isChecked(), self.rotation, self.overrides)
        self.svg = render_svg(self.template.currentData(), self.roles, palette.name)
        self.renderer.load(QByteArray(self.svg.encode("utf-8")))
        border = self.theme.color("border_input")
        for role, button in self.role_buttons.items():
            color = self.roles.colors[role]
            button.setIcon(QIcon(_chip_icon(color, border)))
            source = "pinned" if role in self.overrides else ("palette" if role in self.roles.from_palette else "derived")
            button.setText(ROLE_LABELS[role])
            button.setToolTip(f"{ROLE_LABELS[role]}: {color} ({source})\nClick to choose another color")
        problems = self.roles.contrast_problems()
        if problems:
            self.problems.setText("⚠ Below WCAG AA (4.5:1): " + " · ".join(problems))
            self.problems.setProperty("role", "fail")
        else:
            self.problems.setText("✓ All text in this mockup meets WCAG AA (4.5:1)")
            self.problems.setProperty("role", "pass")
        self.problems.style().unpolish(self.problems)
        self.problems.style().polish(self.problems)
        self.canvas.update()

    def _shuffle(self) -> None:
        self.rotation += 1
        for role in ("primary", "secondary", "accent"):
            self.overrides.pop(role, None)
        self.rebuild()

    def _dark_toggled(self, *_args) -> None:
        for role in ("background", "text", "surface", "border", "muted"):
            self.overrides.pop(role, None)  # pinned light-mode neutrals rarely fit dark mode
        self.rebuild()

    def set_role(self, role: str, color: str | None) -> None:
        """Pin a role to a color, or None to go back to automatic."""
        if color is None:
            self.overrides.pop(role, None)
        else:
            self.overrides[role] = color
        self.rebuild()

    def _fill_role_menu(self, role: str) -> None:
        menu = self.role_buttons[role].menu()
        menu.clear()
        auto = menu.addAction("Automatic")
        auto.setCheckable(True)
        auto.setChecked(role not in self.overrides)
        auto.triggered.connect(lambda: self.set_role(role, None))
        menu.addSeparator()
        border = self.theme.color("border_input")
        for color in dict.fromkeys(self.document.palette.colors):
            action = menu.addAction(QIcon(_chip_icon(color, border)), color)
            action.triggered.connect(lambda _checked=False, c=color: self.set_role(role, c))

    # ----- export -----

    def export_svg(self, path: str | None = None) -> str | None:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export Mockup", f"{self.document.palette.name} mockup.svg", "SVG (*.svg)")
            if not path:
                return None
        try:
            Path(path).write_text(self.svg, encoding="utf-8", newline="\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Mockup", f"Could not write “{Path(path).name}”:\n{exc}")
            return None
        return path

    def export_png(self, path: str | None = None, scale: float = 2.0) -> str | None:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export Mockup", f"{self.document.palette.name} mockup.png", "PNG (*.png)")
            if not path:
                return None
        image = QImage(MOCKUP_SIZE * scale, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
        painter.end()
        if not image.save(path, "PNG"):
            QMessageBox.warning(self, "Export Mockup", f"Could not write “{Path(path).name}”.")
            return None
        return path

    # ----- zoom (same interface as the other document tabs) -----

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.1, min(zoom, ZOOM_STEPS[-1]))
        if abs(zoom - self._zoom) < 1e-6:
            return
        self._zoom = zoom
        self._update_canvas_size()
        self.zoomChanged.emit(zoom)

    def zoom_in(self) -> None:
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom + 1e-6), ZOOM_STEPS[-1]))

    def zoom_out(self) -> None:
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom - 1e-6), ZOOM_STEPS[0]))

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    def fit(self) -> None:
        viewport = self.scroll.viewport().size()
        margin = 32
        self.set_zoom(
            min((viewport.width() - margin) / MOCKUP_SIZE.width(), (viewport.height() - margin) / MOCKUP_SIZE.height())
        )

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            self.fit()

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == event.Type.Resize:
            self._update_canvas_size()
        return super().eventFilter(obj, event)

    def mockup_rect(self) -> QRectF:
        w, h = MOCKUP_SIZE.width() * self._zoom, MOCKUP_SIZE.height() * self._zoom
        return QRectF(max(0, (self.canvas.width() - w) / 2), max(0, (self.canvas.height() - h) / 2), w, h)

    def _update_canvas_size(self) -> None:
        viewport = self.scroll.viewport().size()
        w, h = round(MOCKUP_SIZE.width() * self._zoom), round(MOCKUP_SIZE.height() * self._zoom)
        self.canvas.resize(max(w, viewport.width()), max(h, viewport.height()))
        self.canvas.update()

    def _update_cursor(self, *_args) -> None:
        cursor = tool_cursor(self.theme, self._state.tool)
        if cursor is None:
            self.canvas.unsetCursor()
        else:
            self.canvas.setCursor(cursor)

    def _on_theme_changed(self, *_args) -> None:
        self._update_cursor()
        self.rebuild()
