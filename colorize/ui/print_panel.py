"""Print panel: the active palette proofed through a CMYK profile."""

from pathlib import Path

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from colorize.core.cmyk import INTENT_LABELS, approximate_matches, cached_proofer, find_cmyk_profiles, profile_info
from colorize.ui.color_render import paint_swatch

APPROXIMATE = "approximate"
LOAD = "load"


def split_chip(original: str, printed: str | None, border, size: int = 18) -> QIcon:
    """Left half the screen color, right half how it prints."""
    pixmap = QPixmap(size * 2, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    paint_swatch(p, QRect(0, 0, size + 1, size), original, border)
    paint_swatch(p, QRect(size, 0, size, size), printed or original, border)
    p.end()
    return QIcon(pixmap)


class PrintPanel(QWidget):
    def __init__(self, theme, settings, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._settings = settings
        self._doc = None
        self._proofer = None
        self._proofer_key: tuple[str, str] | None = None  # built lazily, see _ensure_proofer
        self._dirty = True
        self.matches = []

        self.profile = QComboBox()
        self.profile.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.profile.setMinimumContentsLength(10)
        self.intent = QComboBox()
        for key, label in INTENT_LABELS.items():
            self.intent.addItem(label, key)
        self.intent.setCurrentIndex(max(0, self.intent.findData(settings.value("print/intent", "relative", type=str))))
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.addRow("Profile", self.profile)
        form.addRow("Intent", self.intent)

        self.table = QTreeWidget()
        self.table.setRootIsDecorated(False)
        self.table.setHeaderLabels(["Color", "C M Y K %", "ΔE"])
        self.table.setIconSize(QSize(36, 18))
        self.table.setUniformRowHeights(True)
        header = self.table.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.fit_button = QPushButton("Use Print Colors")
        self.fit_button.setToolTip(
            "Replace colors that look noticeably different in print with what the press reproduces "
            "(one undo step), so screen and print agree."
        )
        self.fit_button.clicked.connect(self.use_print_matches)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        buttons.addWidget(self.fit_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._profiles_loaded = False  # scanning system ICC profiles waits until first shown
        self.profile.activated.connect(self._profile_chosen)
        self.intent.currentIndexChanged.connect(self._intent_changed)
        theme.changed.connect(self.refresh)

    # ----- profiles -----

    def _custom_paths(self) -> list[str]:
        value = self._settings.value("print/customProfiles", [], type=list)
        return [p for p in value if p]

    def _fill_profiles(self) -> None:
        self.profile.blockSignals(True)
        self.profile.clear()
        seen = set()
        for path in self._custom_paths():
            info = profile_info(path)
            if info is not None:
                self.profile.addItem(info.description, info.path)
                seen.add(Path(info.path).resolve())
        for info in find_cmyk_profiles():
            if Path(info.path).resolve() not in seen:
                self.profile.addItem(info.description, info.path)
        self.profile.addItem("Approximate (no profile)", APPROXIMATE)
        self.profile.insertSeparator(self.profile.count())
        self.profile.addItem("Load Profile…", LOAD)
        saved = self._settings.value("print/profile", "", type=str)
        index = self.profile.findData(saved) if saved else 0
        self.profile.setCurrentIndex(index if index >= 0 else 0)
        self.profile.blockSignals(False)

    def _profile_chosen(self, index: int) -> None:
        if self.profile.itemData(index) == LOAD:
            self.load_profile()
            return
        self._settings.setValue("print/profile", self.profile.currentData())
        self._build_proofer()

    def load_profile(self, path: str | None = None) -> bool:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Load CMYK Profile", "", "ICC Profiles (*.icc *.icm)")
        if not path:
            self._fill_profiles()  # undo the "Load Profile…" selection
            return False
        if profile_info(path) is None:
            QMessageBox.warning(self, "Load CMYK Profile", f"“{Path(path).name}” is not a CMYK ICC profile.")
            self._fill_profiles()
            return False
        custom = [p for p in self._custom_paths() if p != path]
        self._settings.setValue("print/customProfiles", [path] + custom)
        self._settings.setValue("print/profile", path)
        self._fill_profiles()
        self._build_proofer()
        return True

    def _intent_changed(self, *_args) -> None:
        self._settings.setValue("print/intent", self.intent.currentData())
        self._build_proofer()

    def _build_proofer(self) -> None:
        """Remember which profile/intent to use; the transforms are only built when the
        panel is actually shown (building them costs ~0.8 s)."""
        path = self.profile.currentData()
        self._proofer = None
        self._proofer_key = (path, self.intent.currentData()) if path not in (APPROXIMATE, LOAD, None) else None
        self.intent.setEnabled(self._proofer_key is not None)
        self.refresh()

    def _ensure_proofer(self) -> None:
        if self._proofer is None and self._proofer_key is not None:
            try:
                self._proofer = cached_proofer(*self._proofer_key)
            except ValueError:
                self._proofer_key = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self._profiles_loaded:
            self._profiles_loaded = True
            self._fill_profiles()
            self._build_proofer()  # refreshes
        elif self._dirty:
            self.refresh()

    # ----- document -----

    def set_document(self, doc) -> None:
        if self._doc is not None:
            self._doc.palette.changed.disconnect(self.refresh)
        self._doc = doc
        if doc is not None:
            doc.palette.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        if not self.isVisible():
            self._dirty = True  # recompute when shown
            return
        self._dirty = False
        self._ensure_proofer()
        colors = list(self._doc.palette.colors) if self._doc is not None else []
        self.matches = self._proofer.match(colors) if self._proofer else approximate_matches(colors)
        border = self._theme.color("border_input")
        marks = {"match": "✓ ", "slight": "~ ", "noticeable": "⚠ ", None: ""}
        colors_by_shift = {"match": "success", "slight": "text_muted", "noticeable": "danger"}
        self.table.clear()
        for match in self.matches:
            ink = " ".join(f"{v:.0f}" for v in match.cmyk)
            delta = f"{marks[match.shift]}{match.delta_e:.1f}" if match.delta_e is not None else "–"
            item = QTreeWidgetItem([match.hex, ink, delta])
            item.setIcon(0, split_chip(match.hex, match.print_hex, border))
            if match.shift:
                item.setForeground(2, self._theme.color(colors_by_shift[match.shift]))
            if match.print_hex:
                item.setToolTip(0, f"Prints as {match.print_hex}")
            item.setToolTip(2, "ΔE2000 between screen and print: ≤ 2 same color, 2–5 slight shift, > 5 noticeable")
            self.table.addTopLevelItem(item)
        noticeable = [m for m in self.matches if m.shift == "noticeable"]
        self.fit_button.setEnabled(bool(noticeable))
        if not colors:
            text, role = "Open a palette to check how it prints.", "muted"
        elif self._proofer is None:
            text, role = "Approximate CMYK without a profile: values are only indicative and gamut can't be checked.", "muted"
        elif noticeable:
            text, role = (
                f"⚠ {len(noticeable)} of {len(colors)} colors are outside what "
                f"{self._proofer.info.description} can print and will look noticeably different. "
                "Chips: screen | print.",
                "fail",
            )
        else:
            text, role = f"✓ All colors print close to how they look on {self._proofer.info.description}.", "pass"
        self.summary.setText(text)
        self.summary.setProperty("role", role)
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)

    def use_print_matches(self) -> None:
        if self._doc is None:
            return
        noticeable = [(i, m) for i, m in enumerate(self.matches) if m.shift == "noticeable"]
        if not noticeable:
            return
        stack = self._doc.undo_stack
        stack.beginMacro("Use Print Colors")
        for index, match in noticeable:
            self._doc.set_color(index, match.print_hex)
        stack.endMacro()

