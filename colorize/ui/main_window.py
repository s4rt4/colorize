"""Adobe-style application shell: menus, options bar, tools, dock panels, document tabs."""

import os
from functools import partial
from pathlib import Path

import PyQt6Ads as ads
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QUndoGroup
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from colorize import __version__
from colorize.core.color import format_oklch
from colorize.core.image import IMAGE_SUFFIXES, ImageLoadError, load_image
from colorize.formats import IMPORT_SUFFIXES, colorize_json, import_palette
from colorize.formats.swatch_files import SwatchFileError
from colorize.storage.library import Library
from colorize.model.app_state import AppState
from colorize.model.harmony import HarmonyModel
from colorize.model.palette import Document, Palette
from colorize.core.cvd import cvd_name
from colorize.ui.color_picker import pick_color
from colorize.ui.contrast_panel import ContrastPanel
from colorize.ui.cvd_panel import CvdPanel
from colorize.ui.document_view import DocumentView
from colorize.ui.export_panel import ExportPanel
from colorize.ui.harmony_panel import HarmonyPanel
from colorize.ui.image_view import ImageView
from colorize.ui.library_panel import LibraryPanel
from colorize.ui.options_bar import OptionsBar
from colorize.ui.panels import ColorPanel, HistoryPanel, SwatchesPanel
from colorize.ui.preferences import PreferencesDialog
from colorize.ui.scale_panel import ScalePanel
from colorize.ui.screen_sampler import ScreenSampler
from colorize.ui.themes import THEME_LABELS, THEME_ORDER
from colorize.ui.tools import TOOL_LAYOUT, TOOLS
from colorize.ui.widgets import ColorChip, ForegroundBackground
from colorize.ui.workspaces import CUSTOM_PREFIX, PANEL_WIDTH, WORKSPACE_HEIGHTS, WORKSPACE_LABELS, WORKSPACES

LOGO = Path(__file__).parent / "assets" / "logo.svg"

# Tools that bring their panel forward when chosen.
TOOL_PANELS = {"harmony": "harmony", "contrast": "contrast", "cvd": "cvd"}

SAMPLE_COLORS = ("#1F3A5F", "#3D6A9E", "#7FB2E5", "#F2C14E", "#F78154", "#4D9078", "#B4436C", "#F2F2F2")

_TEXT_INPUTS = (QLineEdit, QAbstractSpinBox, QPlainTextEdit, QTextEdit)


def configure_ads() -> None:
    """Global ADS flags; must run before the CDockManager is created."""
    M = ads.CDockManager
    F = M.eConfigFlag
    A = M.eAutoHideFlag
    M.setConfigFlags(F.DefaultOpaqueConfig)
    for flag, enabled in (
        (F.DisableStylesheet, True),  # our theme QSS styles every ADS widget
        (F.AlwaysShowTabs, True),  # also means ADS never toggles title bars itself
        (F.DisableTabTextEliding, True),
        (F.ActiveTabHasCloseButton, True),
        (F.AllTabsHaveCloseButton, False),
        (F.TabCloseButtonIsToolButton, True),
        (F.DockAreaHasCloseButton, False),
        (F.DockAreaHasUndockButton, False),
        (F.DockAreaHasTabsMenuButton, True),
        (F.DockAreaDynamicTabsMenuButtonVisibility, False),
        (F.HideSingleCentralWidgetTitleBar, True),
        (F.EqualSplitOnInsertion, True),
        (F.FocusHighlighting, False),
        (F.MiddleMouseButtonClosesTab, False),
        (F.FloatingContainerHasWidgetTitle, True),
        (F.FloatingContainerHasWidgetIcon, True),
    ):
        M.setConfigFlag(flag, enabled)
    M.setAutoHideConfigFlags(A.AutoHideFeatureEnabled)
    for flag in (
        A.DockAreaHasAutoHideButton,
        A.AutoHideButtonTogglesArea,
        A.AutoHideSideBarsIconOnly,  # collapsed panels show as an icon strip, like Adobe
        A.AutoHideCloseOnOutsideMouseClick,
        A.AutoHideHasMinimizeButton,
    ):
        M.setAutoHideConfigFlag(flag, True)


class MainWindow(QMainWindow):
    def __init__(self, theme, settings, state: AppState | None = None, library: Library | None = None, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.settings = settings
        self.library = library if library is not None else Library(":memory:")
        self.state = state or AppState(self)
        self.undo_group = QUndoGroup(self)
        self.harmony = HarmonyModel(parent=self)
        self.screen_sampler = ScreenSampler(parent=self)
        self._target_view: DocumentView | None = None  # palette that palette commands act on
        self._doc_counter = 0
        self._workspace = "essentials"
        self._hidden_snapshot = None  # (dock state, tools visible, options visible) while Tab-hidden
        self._expanded_state = None  # dock state before Collapse Panels to Icons
        self._space_prev_tool: str | None = None

        self.setObjectName("mainWindow")
        self.setWindowTitle("Colorize")
        self.resize(1360, 840)

        self._create_actions()
        self._create_dock_manager()
        self._create_tool_bars()
        self._create_menus()
        self._create_status_bar()

        self.state.toolChanged.connect(self._on_tool_changed)
        self.state.colorsChanged.connect(self._update_status)
        self.state.proofChanged.connect(self._update_proof_ui)
        self.state.cvdChanged.connect(self._update_proof_ui)
        self.screen_sampler.picked.connect(self.state.set_foreground)
        self.panels["library"].openRequested.connect(self.open_from_library)
        self.panels["scale"].addRequested.connect(partial(self._add_colors_to_palette, label="Add Scale"))
        self.panels["scale"].newPaletteRequested.connect(partial(self._palette_from_colors, label="New Scale"))
        self.panels["export"].exported.connect(
            lambda path: self.statusBar().showMessage(f"Exported {path}", 4000)
        )
        self.setAcceptDrops(True)
        self.theme.changed.connect(self._sync_theme_actions)
        self.theme.changed.connect(self._hide_panel_tab_icons)
        QApplication.instance().installEventFilter(self)

        self._apply_workspace("essentials")
        self.new_document(sample=True)
        self._restore_settings()
        self._on_tool_changed(self.state.tool)
        self._sync_theme_actions()
        self._after_layout_change()
        self._update_status()
        self._update_proof_ui()

    # ------------------------------------------------------------------ actions

    def _action(self, text, slot=None, shortcut=None, icon=None, checkable=False, tip=None) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            shortcuts = shortcut if isinstance(shortcut, (list, tuple)) else [shortcut]
            action.setShortcuts([QKeySequence(s) for s in shortcuts])
        if slot is not None:
            action.triggered.connect(slot)
        if icon:
            self.theme.bind_icon(action, icon)
        action.setCheckable(checkable)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        # Registered on the window so shortcuts work even while bars/menus are hidden.
        self.addAction(action)
        return action

    def _create_actions(self) -> None:
        a = self._action
        SK = QKeySequence.StandardKey
        self.actions = {
            "new": a("&New Palette", lambda: self.new_document(), SK.New, icon="new"),
            "open": a("&Open…", lambda: self.open_file(), SK.Open),
            "open_image": a("Open &Image…", lambda: self.open_image(), "Ctrl+Shift+O"),
            "export": a("&Export…", self.export_palette, "Ctrl+Shift+E", tip="Export the active palette"),
            "clear_recent": a("&Clear Recent Files", self._clear_recent),
            "save_to_library": a("Save to &Library", self.save_to_library, "Ctrl+Alt+S", icon="plus",
                                 tip="Save the active palette to the library"),
            "import_files": a("Import Files…", self.import_files_to_library,
                              tip="Add palette files (.json, .ase, .gpl) to the library"),
            "save": a("&Save", lambda: self.save_document(), SK.Save),
            "save_as": a("Save &As…", lambda: self.save_document(save_as=True), "Ctrl+Shift+S"),
            "close": a("&Close", lambda: self.close_document(), SK.Close),
            "exit": a("E&xit", self.close, "Ctrl+Q"),
            "delete_swatch": a("&Delete Swatch", self._delete_swatch, SK.Delete, icon="trash", tip="Delete Swatch"),
            "preferences": a("&Preferences…", self.show_preferences, "Ctrl+K"),
            "choose_fg": a("Choose &Foreground Color…", self._choose_foreground),
            "sample_screen": a("Sample &Screen Color", self.sample_screen, "Shift+I", icon="eyedropper",
                               tip="Pick a color from anywhere on screen (Shift+I)"),
            "swap_colors": a("S&wap Colors", self.state.swap_colors, "X"),
            "default_colors": a("&Default Colors", self.state.reset_colors, "D"),
            "add_fg": a("&Add Foreground to Palette", self._add_foreground, icon="plus", tip="New Swatch from Foreground Color"),
            "add_harmony": a("Add &Harmony to Palette", self._add_harmony),
            "replace_swatch": a("&Replace Swatch with Foreground", self._replace_swatch),
            "swatch_to_fg": a("Set Swatch as &Foreground", self._swatch_to_foreground),
            "rename_palette": a("Re&name Palette…", self._rename_palette),
            "zoom_in": a("Zoom &In", lambda: self._with_view("zoom_in"), ["Ctrl+=", "Ctrl++"]),
            "zoom_out": a("Zoom &Out", lambda: self._with_view("zoom_out"), "Ctrl+-"),
            "fit": a("&Fit on Screen", lambda: self._with_view("fit"), "Ctrl+0"),
            "actual_size": a("&100%", lambda: self._with_view("actual_size"), "Ctrl+1"),
            "proof": a("Proof &Colors", self.state.set_proof, "Ctrl+Y", checkable=True,
                       tip="Show canvases as seen with the color vision type chosen in Color Blindness"),
            "collapse_panels": a("&Collapse Panels to Icons", self._set_panels_collapsed, checkable=True),
            "hide_panels": a("Show/&Hide Panels", self._on_tab_pressed, "Tab"),
            "new_workspace": a("&New Workspace…", self._new_workspace),
            "reset_workspace": a("&Reset Workspace", self._reset_workspace),
            "darker": a("&Darker Interface", lambda: self.theme.cycle(-1), "Shift+F1"),
            "lighter": a("&Lighter Interface", lambda: self.theme.cycle(1), "Shift+F2"),
            "about": a("&About Colorize", self._show_about),
        }

        self.undo_action = self.undo_group.createUndoAction(self, "&Undo")
        self.undo_action.setShortcuts(QKeySequence.keyBindings(SK.Undo))
        self.redo_action = self.undo_group.createRedoAction(self, "&Redo")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        self.addActions([self.undo_action, self.redo_action])

        self.tool_group = QActionGroup(self)
        self.tool_actions: dict[str, QAction] = {}
        for tool in TOOLS.values():
            action = self._action(tool.label, partial(self.state.set_tool, tool.key), tool.shortcut, tool.icon, True)
            action.setToolTip(tool.tooltip)
            self.tool_group.addAction(action)
            self.tool_actions[tool.key] = action

        self.theme_group = QActionGroup(self)
        self.theme_actions: dict[str, QAction] = {}
        for name in THEME_ORDER:
            action = self._action(THEME_LABELS[name], partial(self.theme.apply, name), checkable=True)
            self.theme_group.addAction(action)
            self.theme_actions[name] = action

    # ------------------------------------------------------------- dock layout

    def _create_dock_manager(self) -> None:
        configure_ads()
        self.dock_manager = ads.CDockManager(self)

        self.doc_tabs = QTabWidget()
        self.doc_tabs.setObjectName("documents")
        self.doc_tabs.setDocumentMode(True)
        self.doc_tabs.setTabsClosable(True)
        self.doc_tabs.setMovable(True)
        self.doc_tabs.currentChanged.connect(self._on_current_document_changed)
        self.doc_tabs.tabCloseRequested.connect(self.close_document)

        self.center = QStackedWidget()
        self.center.addWidget(self.doc_tabs)
        self.center.addWidget(self._create_home())

        central = ads.CDockWidget(self.dock_manager, "Documents")
        central.setObjectName("documents")
        central.setWidget(self.center, ads.CDockWidget.eInsertMode.ForceNoScrollArea)
        central.setFeatures(ads.CDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.central_dock = central
        self.dock_manager.setCentralWidget(central)
        self.dock_manager.stateRestored.connect(self._after_layout_change)
        self.dock_manager.perspectiveOpened.connect(self._after_layout_change)

        self.panels = {
            "color": ColorPanel(self.theme, self.state, self.actions["add_fg"], self.actions["sample_screen"]),
            "swatches": SwatchesPanel(self.theme, self.actions["add_fg"], self.actions["delete_swatch"]),
            "harmony": HarmonyPanel(self.theme, self.harmony, self.state, self.actions["add_harmony"]),
            "scale": ScalePanel(self.theme, self.state),
            "contrast": ContrastPanel(self.theme, self.state),
            "cvd": CvdPanel(self.theme, self.state),
            "history": HistoryPanel(self.undo_group),
            "export": ExportPanel(self.settings),
            "library": LibraryPanel(self.theme, self.library, self.actions["save_to_library"], self.actions["import_files"]),
        }
        titles = {
            "color": "Color", "swatches": "Swatches", "harmony": "Harmony", "scale": "Scale", "contrast": "Contrast",
            "cvd": "Color Blindness", "history": "History", "export": "Export", "library": "Libraries",
        }
        icons = {"color": "color", "swatches": "swatches", "harmony": "harmony", "scale": "scale", "contrast": "contrast",
                 "cvd": "cvd", "history": "history", "export": "export", "library": "library"}
        self.docks: dict[str, ads.CDockWidget] = {}
        for key, widget in self.panels.items():
            dock = ads.CDockWidget(self.dock_manager, titles[key])
            dock.setObjectName(key)  # stable id for saved layouts
            # AutoScrollArea: panels scroll when squeezed instead of overlapping their contents.
            dock.setWidget(widget, ads.CDockWidget.eInsertMode.AutoScrollArea)
            dock.setMinimumSizeHintMode(ads.CDockWidget.eMinimumSizeHintMode.MinimumSizeHintFromDockWidget)
            self.theme.bind_icon(dock, icons[key])
            self.docks[key] = dock

    def _create_home(self) -> QWidget:
        home = QWidget()
        home.setObjectName("home")
        logo = QLabel()
        logo.setPixmap(QIcon(str(LOGO)).pixmap(96, 96))
        title = QLabel("Colorize")
        title.setProperty("role", "title")
        hint = QLabel("No document is open")
        hint.setProperty("role", "muted")
        button = QPushButton("New Palette")
        button.setProperty("accent", True)
        button.clicked.connect(lambda: self.new_document())
        layout = QVBoxLayout(home)
        layout.addStretch(1)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        for widget in (title, hint, button):
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        return home

    def _create_tool_bars(self) -> None:
        self.options_bar = QToolBar("Options", self)
        self.options_bar.setObjectName("options")
        self.options_bar.setMovable(False)
        self.options_bar.addWidget(OptionsBar(self.theme, self.state, self.actions, self.harmony))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.options_bar)

        self.tools_bar = QToolBar("Tools", self)
        self.tools_bar.setObjectName("tools")
        self.tools_bar.setOrientation(Qt.Orientation.Vertical)
        self.tools_bar.setMovable(False)
        self.tools_bar.setIconSize(QSize(18, 18))
        for tool in TOOL_LAYOUT:
            if tool is None:
                self.tools_bar.addSeparator()
            else:
                self.tools_bar.addAction(self.tool_actions[tool.key])
        self.tools_bar.addSeparator()
        self.tools_bar.addWidget(ForegroundBackground(self.theme, self.state))
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.tools_bar)

    def _create_menus(self) -> None:
        bar = self.menuBar()
        A = self.actions

        file_menu = bar.addMenu("&File")
        file_menu.addActions([A["new"], A["open"], A["open_image"]])
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        file_menu.addSeparator()
        file_menu.addActions([A["close"], A["save"], A["save_as"]])
        file_menu.addSeparator()
        file_menu.addAction(A["export"])
        file_menu.addSeparator()
        file_menu.addAction(A["exit"])

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addActions([self.undo_action, self.redo_action])
        edit_menu.addSeparator()
        edit_menu.addAction(A["delete_swatch"])
        edit_menu.addSeparator()
        edit_menu.addAction(A["preferences"])

        color_menu = bar.addMenu("&Color")
        color_menu.addActions([A["choose_fg"], A["sample_screen"], A["swap_colors"], A["default_colors"]])

        palette_menu = bar.addMenu("&Palette")
        palette_menu.addActions([A["add_fg"], A["add_harmony"], A["replace_swatch"], A["swatch_to_fg"]])
        palette_menu.addSeparator()
        palette_menu.addAction(A["rename_palette"])
        palette_menu.addAction(A["save_to_library"])

        view_menu = bar.addMenu("&View")
        view_menu.addActions([A["zoom_in"], A["zoom_out"], A["fit"], A["actual_size"]])
        view_menu.addSeparator()
        view_menu.addAction(A["proof"])
        view_menu.addSeparator()
        view_menu.addActions([self.options_bar.toggleViewAction(), self.tools_bar.toggleViewAction()])

        window_menu = bar.addMenu("&Window")
        self.workspace_menu = window_menu.addMenu("&Workspace")
        window_menu.addSeparator()
        window_menu.addActions([A["collapse_panels"], A["hide_panels"]])
        theme_menu = window_menu.addMenu("&Interface Theme")
        theme_menu.addActions(list(self.theme_actions.values()))
        theme_menu.addSeparator()
        theme_menu.addActions([A["darker"], A["lighter"]])
        window_menu.addSeparator()
        for dock in sorted(self.docks.values(), key=lambda d: d.windowTitle()):
            window_menu.addAction(dock.toggleViewAction())

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(A["about"])

        self._rebuild_workspace_menu()

    def _create_status_bar(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self.zoom_label = QLabel()
        self.zoom_label.setMinimumWidth(56)
        self.info_label = QLabel()
        self.fg_chip = ColorChip(self.theme, 11)
        self.fg_label = QLabel()
        self.proof_label = QLabel()
        self.proof_label.setProperty("role", "badge")
        bar.addWidget(self.zoom_label)
        bar.addWidget(self.info_label, 1)
        bar.addPermanentWidget(self.proof_label)
        bar.addPermanentWidget(self.fg_chip)
        bar.addPermanentWidget(self.fg_label)

    # --------------------------------------------------------------- documents
    # Tabs hold palettes (DocumentView) and images (ImageView). Palette commands act on
    # the current tab when it is a palette, otherwise on the palette that was active
    # last, so colors sampled from an image can go straight into it.

    def current_tab(self) -> DocumentView | ImageView | None:
        return self.doc_tabs.currentWidget()

    def current_view(self) -> DocumentView | None:
        widget = self.doc_tabs.currentWidget()
        return widget if isinstance(widget, DocumentView) else None

    def current_image_view(self) -> ImageView | None:
        widget = self.doc_tabs.currentWidget()
        return widget if isinstance(widget, ImageView) else None

    def _tabs(self) -> list:
        return [self.doc_tabs.widget(i) for i in range(self.doc_tabs.count())]

    def _palette_views(self) -> list[DocumentView]:
        return [w for w in self._tabs() if isinstance(w, DocumentView)]

    def current_document(self) -> Document | None:
        """The palette that palette commands act on (see above)."""
        view = self.current_view() or self._target_view
        return view.document if view is not None else None

    def documents(self) -> list[Document]:
        return [view.document for view in self._palette_views()]

    def new_document(self, sample: bool = False) -> Document:
        self._doc_counter += 1
        return self._add_document(Palette(f"Untitled-{self._doc_counter}", SAMPLE_COLORS if sample else ()))

    def _add_document(self, palette: Palette) -> Document:
        doc = Document(palette, self)
        self.undo_group.addStack(doc.undo_stack)

        view = DocumentView(doc, self.state, self.theme)
        refresh = partial(self._update_tab, view)
        view.zoomChanged.connect(refresh)
        doc.modifiedChanged.connect(refresh)
        doc.selectionChanged.connect(refresh)
        palette.changed.connect(refresh)
        palette.renamed.connect(refresh)
        view.grid.activated.connect(lambda index, d=doc: self.state.set_foreground(d.palette.color(index)))
        view.grid.contextMenuRequested.connect(self._show_swatch_menu)

        index = self.doc_tabs.addTab(view, "")
        self.doc_tabs.setCurrentIndex(index)
        self._update_tab(view)
        return doc

    def close_document(self, index: int | None = None) -> bool:
        """Close a tab, asking to save unsaved palette changes. False if the user cancelled."""
        if index is None:
            index = self.doc_tabs.currentIndex()
        widget = self.doc_tabs.widget(index)
        if widget is None:
            return True
        if isinstance(widget, DocumentView) and not self._confirm_discard(widget.document):
            return False
        self.doc_tabs.removeTab(self.doc_tabs.indexOf(widget))
        if widget is self._target_view:
            self._target_view = None
        if isinstance(widget, DocumentView):
            self.undo_group.removeStack(widget.document.undo_stack)
            widget.document.deleteLater()
        widget.deleteLater()
        self._on_current_document_changed(self.doc_tabs.currentIndex())
        return True

    def _on_current_document_changed(self, _index: int) -> None:
        current = self.current_view()
        if current is not None:
            self._target_view = current
        elif self._target_view is None:
            palettes = self._palette_views()
            self._target_view = palettes[-1] if palettes else None
        doc = self.current_document()
        self.undo_group.setActiveStack(doc.undo_stack if doc else None)
        self.panels["swatches"].set_document(doc)
        self.panels["cvd"].set_document(doc)
        self.panels["export"].set_document(doc)
        self.center.setCurrentIndex(0 if self.doc_tabs.count() else 1)
        self._refresh_document_ui()

    def _update_tab(self, view, *_args) -> None:
        index = self.doc_tabs.indexOf(view)
        if index < 0:
            return
        if isinstance(view, DocumentView):
            star = "*" if view.document.is_modified else ""
            self.doc_tabs.setTabToolTip(index, view.document.path or "Not saved yet")
        else:
            star = ""
            self.doc_tabs.setTabToolTip(index, view.path)
        self.doc_tabs.setTabText(index, f"{view.title}{star} @ {round(view.zoom * 100)}%")
        if view is self.current_tab() or view is self._target_view:
            self._refresh_document_ui()

    def _refresh_document_ui(self) -> None:
        doc = self.current_document()
        tab = self.current_tab()
        image = self.current_image_view()
        has_selection = doc is not None and doc.selected >= 0
        for key in ("add_fg", "add_harmony", "rename_palette", "save_to_library", "export"):
            self.actions[key].setEnabled(doc is not None)
        for key in ("save", "save_as"):
            self.actions[key].setEnabled(self.current_view() is not None)
        for key in ("close", "zoom_in", "zoom_out", "fit", "actual_size"):
            self.actions[key].setEnabled(tab is not None)
        for key in ("delete_swatch", "replace_swatch", "swatch_to_fg"):
            self.actions[key].setEnabled(has_selection)
        self.setWindowTitle(f"{tab.title} — Colorize" if tab is not None else "Colorize")
        self.zoom_label.setText(f"{round(tab.zoom * 100)}%" if tab is not None else "")
        if image is not None:
            text = image.info.text()
            if doc is not None:
                text += f"  ·  adding to “{doc.palette.name}”"
            self.info_label.setText(text)
        elif doc is not None:
            n = len(doc.palette)
            text = f"{n} swatch" + ("" if n == 1 else "es")
            if has_selection:
                text += f"  ·  selected {doc.palette.color(doc.selected)}"
            self.info_label.setText(text)
        else:
            self.info_label.setText("")

    def _with_view(self, method: str) -> None:
        tab = self.current_tab()
        if tab is not None:
            getattr(tab, method)()

    # ------------------------------------------------------------------ files

    def _last_dir(self) -> str:
        return self.settings.value("files/lastDir", str(Path.home()), type=str)

    def _remember_dir(self, path: str) -> None:
        self.settings.setValue("files/lastDir", str(Path(path).parent))

    def _find_tab(self, path: str):
        target = os.path.normcase(os.path.abspath(path))
        for widget in self._tabs():
            own = widget.document.path if isinstance(widget, DocumentView) else widget.path
            if own and os.path.normcase(os.path.abspath(own)) == target:
                return widget
        return None

    def open_file(self, path: str | None = None):
        """Open a palette (.json) or an image, by dialog or path. Returns the Document,
        the ImageView, or None."""
        if path is None:
            images = " ".join(f"*{suffix}" for suffix in IMAGE_SUFFIXES)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open",
                self._last_dir(),
                f"All Supported (*{colorize_json.SUFFIX} *.ase *.gpl {images});;{colorize_json.FILE_FILTER};;"
                f"Swatches (*.ase *.gpl);;Images ({images});;All Files (*)",
            )
            if not path:
                return None
        if Path(path).suffix.lower() in IMAGE_SUFFIXES:
            return self.open_image(path)
        if Path(path).suffix.lower() in (".ase", ".gpl"):
            return self.import_swatch_file(path)
        existing = self._find_tab(path)
        if existing is not None:
            self.doc_tabs.setCurrentWidget(existing)
            return existing.document
        try:
            name, colors = colorize_json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, colorize_json.PaletteFormatError) as exc:
            QMessageBox.warning(self, "Open Palette", f"Could not open “{Path(path).name}”:\n{exc}")
            return None
        doc = self._add_document(Palette(name, colors))
        doc.path = str(Path(path))
        self._remember_dir(path)
        self.library.add_recent(path)
        self._update_tab(self.current_view())
        return doc

    def import_swatch_file(self, path: str) -> Document | None:
        """Open an .ase/.gpl as a new, unsaved palette (it is not our file format to save over)."""
        try:
            name, colors = import_palette(path)
        except (OSError, SwatchFileError, colorize_json.PaletteFormatError) as exc:
            QMessageBox.warning(self, "Import Swatches", f"Could not import “{Path(path).name}”:\n{exc}")
            return None
        doc = self._add_document(Palette(name))
        doc.add_colors(colors, "Import Swatches")
        self._remember_dir(path)
        self.library.add_recent(path)
        return doc

    def open_image(self, path: str | None = None) -> ImageView | None:
        if path is None:
            images = " ".join(f"*{suffix}" for suffix in IMAGE_SUFFIXES)
            path, _ = QFileDialog.getOpenFileName(self, "Open Image", self._last_dir(), f"Images ({images})")
            if not path:
                return None
        existing = self._find_tab(path)
        if existing is not None:
            self.doc_tabs.setCurrentWidget(existing)
            return existing
        try:
            image = load_image(path)
        except ImageLoadError as exc:
            QMessageBox.warning(self, "Open Image", f"Could not open “{Path(path).name}”:\n{exc}")
            return None
        view = ImageView(path, image, self.state, self.theme)
        view.zoomChanged.connect(partial(self._update_tab, view))
        view.createPaletteRequested.connect(self._palette_from_colors)
        view.addToPaletteRequested.connect(self._add_colors_to_palette)
        self.doc_tabs.setCurrentIndex(self.doc_tabs.addTab(view, ""))
        self._update_tab(view)
        self._remember_dir(path)
        self.library.add_recent(path)
        return view

    def _palette_from_colors(self, name: str, colors: list, label: str = "Extract from Image") -> Document:
        doc = self._add_document(Palette(name))
        doc.add_colors(colors, label)  # undoable, and marks the palette unsaved
        return doc

    def _add_colors_to_palette(self, colors: list, label: str = "Add Image Colors") -> None:
        doc = self.current_document()
        if doc is None:
            self._palette_from_colors("Untitled", colors)
            return
        doc.add_colors(colors, label)
        self.statusBar().showMessage(f"Added {len(colors)} colors to “{doc.palette.name}”", 4000)

    def _rebuild_recent_menu(self) -> None:
        menu = self.recent_menu
        menu.clear()
        recent = self.library.recent_files()
        for path in recent:
            action = menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(partial(self._open_recent, path))
        if not recent:
            menu.addAction("No Recent Files").setEnabled(False)
        menu.addSeparator()
        menu.addAction(self.actions["clear_recent"])
        self.actions["clear_recent"].setEnabled(bool(recent))

    def _open_recent(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "Open Recent", f"“{Path(path).name}” no longer exists:\n{path}")
            self.library.remove_recent(path)
            return
        self.open_file(path)

    def _clear_recent(self) -> None:
        self.library.clear_recent()

    # ---------------------------------------------------------------- library

    def save_to_library(self) -> int | None:
        """Store the active palette in the library (updating its entry if it has one).
        A palette with no file counts as saved afterwards."""
        doc = self.current_document()
        if doc is None:
            return None
        name, colors = doc.palette.name, list(doc.palette.colors)
        if doc.library_id is not None and self.library.get_palette(doc.library_id) is not None:
            self.library.update_palette(doc.library_id, name, colors)
        else:
            doc.library_id = self.library.add_palette(name, colors)
        if doc.path is None:
            doc.undo_stack.setClean()
        panel = self.panels["library"]
        panel.refresh()
        panel.select_id(doc.library_id)
        self.statusBar().showMessage(f"Saved “{name}” to the library", 4000)
        return doc.library_id

    def open_from_library(self, palette) -> Document:
        for view in self._palette_views():
            if view.document.library_id == palette.id:
                self.doc_tabs.setCurrentWidget(view)
                return view.document
        doc = self._add_document(Palette(palette.name, palette.colors))
        doc.library_id = palette.id
        return doc

    def import_files_to_library(self, paths=None) -> int:
        """Bulk-add palette files to the library; how saved JSON palettes move into SQLite."""
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Import Palettes to Library", self._last_dir(), "Palettes (*.json *.ase *.gpl)"
            )
        added, failed = 0, []
        for path in paths:
            try:
                name, colors = import_palette(path)
            except (OSError, UnicodeDecodeError, SwatchFileError, colorize_json.PaletteFormatError) as exc:
                failed.append(f"{Path(path).name}: {exc}")
                continue
            self.library.add_palette(name, colors)
            added += 1
        if paths:
            self._remember_dir(paths[0])
        self.panels["library"].refresh()
        if failed:
            QMessageBox.warning(self, "Import Palettes", "Some files were skipped:\n" + "\n".join(failed))
        if added:
            self.statusBar().showMessage(f"Added {added} palette{'s' if added > 1 else ''} to the library", 4000)
        return added

    def export_palette(self) -> str | None:
        dock = self.docks["export"]
        if dock.isClosed():
            dock.toggleView(True)
        dock.setAsCurrentTab()
        return self.panels["export"].export_file()

    def sample_screen(self) -> None:
        self.screen_sampler.start(self.state.sample_size)

    @staticmethod
    def _dropped_paths(mime) -> list[str]:
        accepted = IMAGE_SUFFIXES + IMPORT_SUFFIXES
        return [
            url.toLocalFile()
            for url in mime.urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in accepted
        ]

    def dragEnterEvent(self, event) -> None:
        if self._dropped_paths(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = self._dropped_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            for path in paths:
                self.open_file(path)

    def save_document(self, doc: Document | None = None, save_as: bool = False) -> bool:
        """Save (or Save As). Returns False if cancelled or failed."""
        doc = doc or (self.current_view().document if self.current_view() else None)
        if doc is None:
            return False
        path = doc.path
        if save_as or not path:
            folder = os.path.dirname(path) if path else self._last_dir()
            start = os.path.join(folder, f"{doc.palette.name}{colorize_json.SUFFIX}")
            path, _ = QFileDialog.getSaveFileName(self, "Save Palette As", start, colorize_json.FILE_FILTER)
            if not path:
                return False
            if not path.lower().endswith(colorize_json.SUFFIX):
                path += colorize_json.SUFFIX
        try:
            _write_atomic(Path(path), colorize_json.dumps(doc.palette.name, doc.palette.colors))
        except OSError as exc:
            QMessageBox.warning(self, "Save Palette", f"Could not save “{Path(path).name}”:\n{exc}")
            return False
        doc.path = str(Path(path))
        doc.undo_stack.setClean()
        self._remember_dir(path)
        self.library.add_recent(path)
        for view in self._palette_views():
            if view.document is doc:
                self._update_tab(view)
        self.statusBar().showMessage(f"Saved {doc.path}", 4000)
        return True

    def ask_save_changes(self, doc: Document) -> str:
        """'save', 'discard' or 'cancel'. A separate method so tests can answer it."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Colorize")
        box.setText(f"Save changes to “{doc.palette.name}” before closing?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Save:
            return "save"
        if answer == QMessageBox.StandardButton.Discard:
            return "discard"
        return "cancel"

    def _confirm_discard(self, doc: Document) -> bool:
        """True when it is fine to drop ``doc``: unmodified, saved now, or discarded."""
        if not doc.is_modified:
            return True
        for view in self._palette_views():
            if view.document is doc:
                self.doc_tabs.setCurrentWidget(view)
        answer = self.ask_save_changes(doc)
        if answer == "save":
            return self.save_document(doc)
        return answer == "discard"

    # ----------------------------------------------------------- palette edits

    def _add_foreground(self) -> None:
        doc = self.current_document()
        if doc:
            doc.add_color(self.state.foreground)

    def _delete_swatch(self) -> None:
        doc = self.current_document()
        if doc and doc.selected >= 0:
            doc.remove_color(doc.selected)

    def _replace_swatch(self) -> None:
        doc = self.current_document()
        if doc and doc.selected >= 0:
            doc.set_color(doc.selected, self.state.foreground)

    def _swatch_to_foreground(self) -> None:
        doc = self.current_document()
        if doc and doc.selected >= 0:
            self.state.set_foreground(doc.palette.color(doc.selected))

    def _rename_palette(self) -> None:
        doc = self.current_document()
        if not doc:
            return
        name, ok = QInputDialog.getText(self, "Rename Palette", "Name:", text=doc.palette.name)
        if ok:
            doc.rename(name)

    def _add_harmony(self) -> None:
        doc = self.current_document()
        if doc:
            doc.add_colors(self.harmony.hexes(), "Add Harmony")

    def _choose_foreground(self) -> None:
        color = pick_color(self.theme, self, self.state.foreground, "Foreground Color")
        if color:
            self.state.set_foreground(color)

    def _show_swatch_menu(self, _index: int, global_pos) -> None:
        menu = QMenu(self)
        menu.addActions([self.actions["swatch_to_fg"], self.actions["replace_swatch"]])
        menu.addSeparator()
        menu.addAction(self.actions["delete_swatch"])
        menu.exec(global_pos)

    # ------------------------------------------------------------------- tools

    def _on_tool_changed(self, key: str) -> None:
        self.tool_actions[key].setChecked(True)
        if key in TOOL_PANELS:
            dock = self.docks[TOOL_PANELS[key]]
            if dock.isClosed():
                dock.toggleView(True)
            dock.setAsCurrentTab()

    def eventFilter(self, obj, event):
        """Hold Space for the Hand tool, release to go back (Photoshop behavior)."""
        kind = event.type()
        if kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and event.key() == Qt.Key.Key_Space:
            if QApplication.activeWindow() is not self or isinstance(QApplication.focusWidget(), _TEXT_INPUTS):
                return False
            if event.isAutoRepeat():
                return self._space_prev_tool is not None
            if kind == QEvent.Type.KeyPress and self._space_prev_tool is None and self.state.tool != "hand":
                self._space_prev_tool = self.state.tool
                self.state.set_tool("hand")
                return True
            if kind == QEvent.Type.KeyRelease and self._space_prev_tool is not None:
                self.state.set_tool(self._space_prev_tool)
                self._space_prev_tool = None
                return True
        return False

    # ------------------------------------------------------------- workspaces

    def _apply_workspace(self, key: str) -> None:
        """Rearrange panels into a built-in workspace."""
        self._leave_transient_layouts()
        manager = self.dock_manager
        for dock in self.docks.values():
            if dock.isAutoHide():
                dock.setAutoHide(False)
        placed = set()
        previous = None
        areas = []
        for group in WORKSPACES[key]:
            area = None
            for panel in group:
                dock = self.docks[panel]
                if area is None:
                    if previous is None:
                        area = manager.addDockWidget(ads.DockWidgetArea.RightDockWidgetArea, dock)
                    else:
                        area = manager.addDockWidget(ads.DockWidgetArea.BottomDockWidgetArea, dock, previous)
                else:
                    manager.addDockWidgetTabToArea(dock, area)
                dock.toggleView(True)
                placed.add(panel)
            area.setCurrentIndex(0)
            areas.append(area)
            previous = area
        for panel, dock in self.docks.items():
            if panel not in placed:
                dock.toggleView(False)
        self._workspace = key
        self._rebuild_workspace_menu()
        self._after_layout_change()
        QTimer.singleShot(0, partial(self._apply_panel_sizes, areas, WORKSPACE_HEIGHTS[key]))

    def _apply_panel_sizes(self, areas, heights) -> None:
        """Panel column width and group heights. Splitters can still hold hidden areas left
        over from the previous layout (closed panels), so only visible parts get space."""
        central = self.central_dock.dockAreaWidget()
        row = central.parentWidget() if central is not None else None
        if isinstance(row, QSplitter):
            sizes = row.sizes()
            others = [i for i in range(row.count()) if row.widget(i) is not central and not row.widget(i).isHidden()]
            if others and sum(sizes) > PANEL_WIDTH * (len(others) + 1):
                new = [0] * len(sizes)
                for i in others:
                    new[i] = PANEL_WIDTH
                new[row.indexOf(central)] = sum(sizes) - PANEL_WIDTH * len(others)
                row.setSizes(new)
        column = areas[0].parentWidget() if areas else None
        if isinstance(column, QSplitter) and column.orientation() == Qt.Orientation.Vertical:
            weight = {id(area): h for area, h in zip(areas, heights)}
            total = sum(column.sizes())
            column.setSizes(
                [round(total * weight.get(id(column.widget(i)), 0) / sum(heights)) for i in range(column.count())]
            )

    def _after_layout_change(self, *_args) -> None:
        # Documents sit directly under the options bar, with no dock title bar (restored
        # layouts may rebuild the area, so look it up each time).
        area = self.central_dock.dockAreaWidget()
        if area is not None:
            area.titleBar().hide()
        self._hide_panel_tab_icons()

    def _open_custom_workspace(self, name: str) -> None:
        self._leave_transient_layouts()
        self.dock_manager.openPerspective(name)
        self._workspace = CUSTOM_PREFIX + name
        self._rebuild_workspace_menu()

    def _reset_workspace(self) -> None:
        if self._workspace.startswith(CUSTOM_PREFIX):
            self._open_custom_workspace(self._workspace[len(CUSTOM_PREFIX):])
        else:
            self._apply_workspace(self._workspace)

    def _new_workspace(self) -> None:
        name, ok = QInputDialog.getText(self, "New Workspace", "Name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in WORKSPACE_LABELS.values():
            QMessageBox.warning(self, "New Workspace", f"“{name}” is a built-in workspace. Choose another name.")
            return
        self.dock_manager.addPerspective(name)
        self._workspace = CUSTOM_PREFIX + name
        self._rebuild_workspace_menu()

    def _delete_workspace(self, name: str) -> None:
        self.dock_manager.removePerspective(name)
        if self._workspace == CUSTOM_PREFIX + name:
            self._workspace = "essentials"
        self._rebuild_workspace_menu()

    def _rebuild_workspace_menu(self) -> None:
        menu = self.workspace_menu
        menu.clear()
        group = QActionGroup(menu)
        for key, label in WORKSPACE_LABELS.items():
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._workspace == key)
            action.triggered.connect(partial(self._apply_workspace, key))
            group.addAction(action)
        custom = list(self.dock_manager.perspectiveNames())
        if custom:
            menu.addSeparator()
            for name in custom:
                action = menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(self._workspace == CUSTOM_PREFIX + name)
                action.triggered.connect(partial(self._open_custom_workspace, name))
                group.addAction(action)
        menu.addSeparator()
        current = self._workspace
        label = current[len(CUSTOM_PREFIX):] if current.startswith(CUSTOM_PREFIX) else WORKSPACE_LABELS[current]
        self.actions["reset_workspace"].setText(f"Reset {label}")
        menu.addActions([self.actions["reset_workspace"], self.actions["new_workspace"]])
        if custom:
            delete_menu = menu.addMenu("Delete Workspace")
            for name in custom:
                delete_menu.addAction(name).triggered.connect(partial(self._delete_workspace, name))

    # ------------------------------------------- collapse / hide all panels

    def _set_panels_collapsed(self, collapsed: bool) -> None:
        """Window > Collapse Panels to Icons: docked panels shrink to an icon strip."""
        if self._hidden_snapshot is not None:
            self._show_panels()
        if collapsed:
            self._expanded_state = self.dock_manager.saveState()
            for dock in self.docks.values():
                if not dock.isClosed() and not dock.isFloating() and not dock.isAutoHide():
                    dock.setAutoHide(True, ads.SideBarLocation.SideBarRight)
        else:
            if self._expanded_state is not None:
                self.dock_manager.restoreState(self._expanded_state)
            else:
                for dock in self.docks.values():
                    if dock.isAutoHide():
                        dock.setAutoHide(False)
            self._expanded_state = None
        self.actions["collapse_panels"].setChecked(collapsed)

    def _on_tab_pressed(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, _TEXT_INPUTS):  # Tab inside a field keeps its normal meaning
            self.focusNextChild()
            return
        if self._hidden_snapshot is None:
            self._hide_panels()
        else:
            self._show_panels()

    def _hide_panels(self) -> None:
        self._hidden_snapshot = (
            self.dock_manager.saveState(),
            self.tools_bar.isVisible(),
            self.options_bar.isVisible(),
        )
        for dock in self.docks.values():
            dock.toggleView(False)
        self.tools_bar.hide()
        self.options_bar.hide()

    def _show_panels(self) -> None:
        state, tools_visible, options_visible = self._hidden_snapshot
        self._hidden_snapshot = None
        self.dock_manager.restoreState(state)
        self.tools_bar.setVisible(tools_visible)
        self.options_bar.setVisible(options_visible)

    @property
    def panels_hidden(self) -> bool:
        return self._hidden_snapshot is not None

    def _leave_transient_layouts(self) -> None:
        if self._hidden_snapshot is not None:
            self._show_panels()
        self._expanded_state = None
        self.actions["collapse_panels"].setChecked(False)

    # ------------------------------------------------------------ theme/misc

    def _hide_panel_tab_icons(self, *_args) -> None:
        """Adobe panel tabs are text-only; icons appear only in the collapsed icon strip.
        ADS re-shows the icon label whenever the icon changes, so this runs after each theme change."""
        for dock in self.docks.values():
            for label in dock.tabWidget().findChildren(QLabel):
                if label.objectName() != "dockWidgetTabLabel":
                    label.hide()

    def _sync_theme_actions(self, *_args) -> None:
        self.theme_actions[self.theme.name].setChecked(True)
        self.actions["darker"].setEnabled(self.theme.name != THEME_ORDER[0])
        self.actions["lighter"].setEnabled(self.theme.name != THEME_ORDER[-1])

    def _update_proof_ui(self, *_args) -> None:
        on = self.state.proof
        self.actions["proof"].setChecked(on)
        self.proof_label.setVisible(on)
        if on:
            self.proof_label.setText(f"Proof: {cvd_name(self.state.cvd_type, self.state.cvd_severity)}")

    def _update_status(self) -> None:
        fg = self.state.foreground
        self.fg_chip.set_color(fg)
        self.fg_label.setText(f"{fg}  ·  {format_oklch(fg)}")

    def show_preferences(self) -> None:
        PreferencesDialog(self.theme, self).exec()

    def _show_about(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("About Colorize")
        box.setIconPixmap(QIcon(str(LOGO)).pixmap(72, 72))
        box.setText(f"<b>Colorize</b> {__version__}")
        box.setInformativeText(
            "Offline color manager.<br><br>MIT License.<br>"
            "Interface font: Source Sans 3 (SIL Open Font License)."
        )
        box.exec()

    # --------------------------------------------------------------- settings

    def _restore_settings(self) -> None:
        s = self.settings
        geometry = s.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        window_state = s.value("window/state")
        if window_state is not None:
            self.restoreState(window_state)

        self.dock_manager.loadPerspectives(s)
        workspace = s.value("workspace/name", "essentials", type=str)
        if workspace in WORKSPACES:
            self._workspace = workspace
        elif workspace.startswith(CUSTOM_PREFIX) and workspace[len(CUSTOM_PREFIX):] in self.dock_manager.perspectiveNames():
            self._workspace = workspace
        dock_state = s.value("workspace/state")
        if dock_state is not None:
            self.dock_manager.restoreState(dock_state)
        expanded = s.value("workspace/expandedState")
        if expanded is not None:
            self._expanded_state = expanded
            self.actions["collapse_panels"].setChecked(True)
        self._rebuild_workspace_menu()

    def save_settings(self) -> None:
        if self._hidden_snapshot is not None:
            self._show_panels()
        s = self.settings
        s.setValue("ui/theme", self.theme.name)
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())
        s.setValue("workspace/name", self._workspace)
        s.setValue("workspace/state", self.dock_manager.saveState())
        if self._expanded_state is not None:
            s.setValue("workspace/expandedState", self._expanded_state)
        else:
            s.remove("workspace/expandedState")
        self.dock_manager.savePerspectives(s)
        s.sync()

    def closeEvent(self, event) -> None:
        for doc in self.documents():
            if not self._confirm_discard(doc):
                event.ignore()
                return
        self.save_settings()
        QApplication.instance().removeEventFilter(self)
        self.dock_manager.deleteLater()
        super().closeEvent(event)


def _write_atomic(path: Path, text: str) -> None:
    """Write to a temp file, then replace, so a failed save never truncates the old file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
