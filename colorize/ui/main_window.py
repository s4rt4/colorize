"""Adobe-style application shell: menus, options bar, tools, dock panels, document tabs."""

from functools import partial

import PyQt6Ads as ads
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence, QUndoGroup
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from colorize import __version__
from colorize.core.color import format_oklch
from colorize.model.app_state import AppState
from colorize.model.palette import Document, Palette
from colorize.ui.document_view import DocumentView
from colorize.ui.options_bar import OptionsBar
from colorize.ui.panels import ColorPanel, HistoryPanel, PlaceholderPanel, SwatchesPanel
from colorize.ui.preferences import PreferencesDialog
from colorize.ui.themes import THEME_LABELS, THEME_ORDER
from colorize.ui.tools import TOOL_LAYOUT, TOOLS
from colorize.ui.widgets import ColorChip, ForegroundBackground, pick_color
from colorize.ui.workspaces import CUSTOM_PREFIX, PANEL_WIDTH, WORKSPACE_LABELS, WORKSPACES

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
    def __init__(self, theme, settings, state: AppState | None = None, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.settings = settings
        self.state = state or AppState(self)
        self.undo_group = QUndoGroup(self)
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
            "open": a("&Open…", shortcut=SK.Open, tip="Arrives in M1"),
            "save": a("&Save", shortcut=SK.Save, tip="Arrives in M1"),
            "save_as": a("Save &As…", shortcut="Ctrl+Shift+S", tip="Arrives in M1"),
            "close": a("&Close", lambda: self.close_document(), SK.Close),
            "exit": a("E&xit", self.close, "Ctrl+Q"),
            "delete_swatch": a("&Delete Swatch", self._delete_swatch, SK.Delete, icon="trash", tip="Delete Swatch"),
            "preferences": a("&Preferences…", self.show_preferences, "Ctrl+K"),
            "choose_fg": a("Choose &Foreground Color…", self._choose_foreground),
            "swap_colors": a("S&wap Colors", self.state.swap_colors, "X"),
            "default_colors": a("&Default Colors", self.state.reset_colors, "D"),
            "add_fg": a("&Add Foreground to Palette", self._add_foreground, icon="plus", tip="New Swatch from Foreground Color"),
            "replace_swatch": a("&Replace Swatch with Foreground", self._replace_swatch),
            "swatch_to_fg": a("Set Swatch as &Foreground", self._swatch_to_foreground),
            "rename_palette": a("Re&name Palette…", self._rename_palette),
            "zoom_in": a("Zoom &In", lambda: self._with_view("zoom_in"), ["Ctrl+=", "Ctrl++"]),
            "zoom_out": a("Zoom &Out", lambda: self._with_view("zoom_out"), "Ctrl+-"),
            "fit": a("&Fit on Screen", lambda: self._with_view("fit"), "Ctrl+0"),
            "actual_size": a("&100%", lambda: self._with_view("actual_size"), "Ctrl+1"),
            "collapse_panels": a("&Collapse Panels to Icons", self._set_panels_collapsed, checkable=True),
            "hide_panels": a("Show/&Hide Panels", self._on_tab_pressed, "Tab"),
            "new_workspace": a("&New Workspace…", self._new_workspace),
            "reset_workspace": a("&Reset Workspace", self._reset_workspace),
            "darker": a("&Darker Interface", lambda: self.theme.cycle(-1), "Shift+F1"),
            "lighter": a("&Lighter Interface", lambda: self.theme.cycle(1), "Shift+F2"),
            "about": a("&About Colorize", self._show_about),
        }
        for key in ("open", "save", "save_as"):
            self.actions[key].setEnabled(False)

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
            "color": ColorPanel(self.theme, self.state, self.actions["add_fg"]),
            "swatches": SwatchesPanel(self.theme, self.actions["add_fg"], self.actions["delete_swatch"]),
            "harmony": PlaceholderPanel(
                self.theme, "harmony", "Harmony", "M1",
                "OKLCH color wheel with complementary, analogous, triadic, tetradic, split and monochromatic rules.",
            ),
            "contrast": PlaceholderPanel(
                self.theme, "contrast", "Contrast", "M3",
                "WCAG 2.x and APCA contrast with lightness suggestions to pass AA/AAA.",
            ),
            "cvd": PlaceholderPanel(
                self.theme, "cvd", "Color Blindness", "M3",
                "Protan, deutan and tritan simulation with severity (Machado 2009).",
            ),
            "history": HistoryPanel(self.undo_group),
            "export": PlaceholderPanel(
                self.theme, "export", "Export", "M4",
                "CSS variables, Tailwind v3/v4, W3C design tokens, ASE and GPL.",
            ),
        }
        titles = {
            "color": "Color", "swatches": "Swatches", "harmony": "Harmony", "contrast": "Contrast",
            "cvd": "Color Blindness", "history": "History", "export": "Export",
        }
        icons = {"color": "color", "swatches": "swatches", "harmony": "harmony", "contrast": "contrast",
                 "cvd": "cvd", "history": "history", "export": "export"}
        self.docks: dict[str, ads.CDockWidget] = {}
        for key, widget in self.panels.items():
            dock = ads.CDockWidget(self.dock_manager, titles[key])
            dock.setObjectName(key)  # stable id for saved layouts
            dock.setWidget(widget, ads.CDockWidget.eInsertMode.ForceNoScrollArea)
            dock.setMinimumSizeHintMode(ads.CDockWidget.eMinimumSizeHintMode.MinimumSizeHintFromDockWidget)
            self.theme.bind_icon(dock, icons[key])
            self.docks[key] = dock

    def _create_home(self) -> QWidget:
        home = QWidget()
        home.setObjectName("home")
        title = QLabel("Colorize")
        title.setProperty("role", "title")
        hint = QLabel("No palette is open")
        hint.setProperty("role", "muted")
        button = QPushButton("New Palette")
        button.setProperty("accent", True)
        button.clicked.connect(lambda: self.new_document())
        layout = QVBoxLayout(home)
        layout.addStretch(1)
        for widget in (title, hint, button):
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        return home

    def _create_tool_bars(self) -> None:
        self.options_bar = QToolBar("Options", self)
        self.options_bar.setObjectName("options")
        self.options_bar.setMovable(False)
        self.options_bar.addWidget(OptionsBar(self.theme, self.state, self.actions))
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
        file_menu.addActions([A["new"], A["open"]])
        file_menu.addSeparator()
        file_menu.addActions([A["close"], A["save"], A["save_as"]])
        file_menu.addSeparator()
        file_menu.addAction(A["exit"])

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addActions([self.undo_action, self.redo_action])
        edit_menu.addSeparator()
        edit_menu.addAction(A["delete_swatch"])
        edit_menu.addSeparator()
        edit_menu.addAction(A["preferences"])

        color_menu = bar.addMenu("&Color")
        color_menu.addActions([A["choose_fg"], A["swap_colors"], A["default_colors"]])

        palette_menu = bar.addMenu("&Palette")
        palette_menu.addActions([A["add_fg"], A["replace_swatch"], A["swatch_to_fg"]])
        palette_menu.addSeparator()
        palette_menu.addAction(A["rename_palette"])

        view_menu = bar.addMenu("&View")
        view_menu.addActions([A["zoom_in"], A["zoom_out"], A["fit"], A["actual_size"]])
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
        bar.addWidget(self.zoom_label)
        bar.addWidget(self.info_label, 1)
        bar.addPermanentWidget(self.fg_chip)
        bar.addPermanentWidget(self.fg_label)

    # --------------------------------------------------------------- documents

    def current_view(self) -> DocumentView | None:
        widget = self.doc_tabs.currentWidget()
        return widget if isinstance(widget, DocumentView) else None

    def current_document(self) -> Document | None:
        view = self.current_view()
        return view.document if view else None

    def documents(self) -> list[Document]:
        return [self.doc_tabs.widget(i).document for i in range(self.doc_tabs.count())]

    def new_document(self, sample: bool = False) -> Document:
        self._doc_counter += 1
        palette = Palette(f"Untitled-{self._doc_counter}", SAMPLE_COLORS if sample else ())
        doc = Document(palette, self)
        self.undo_group.addStack(doc.undo_stack)

        view = DocumentView(doc, self.state, self.theme)
        refresh = partial(self._on_document_edited, view)
        view.zoomChanged.connect(refresh)
        doc.modifiedChanged.connect(refresh)
        doc.selectionChanged.connect(refresh)
        palette.changed.connect(refresh)
        palette.renamed.connect(refresh)
        view.grid.activated.connect(lambda index, d=doc: self.state.set_foreground(d.palette.color(index)))
        view.grid.contextMenuRequested.connect(self._show_swatch_menu)

        index = self.doc_tabs.addTab(view, "")
        self.doc_tabs.setCurrentIndex(index)
        self._on_document_edited(view)
        return doc

    def close_document(self, index: int | None = None) -> None:
        if index is None:
            index = self.doc_tabs.currentIndex()
        view = self.doc_tabs.widget(index)
        if not isinstance(view, DocumentView):
            return
        self.doc_tabs.removeTab(index)
        if self.doc_tabs.count() == 0:
            self._on_current_document_changed(-1)
        self.undo_group.removeStack(view.document.undo_stack)
        view.deleteLater()
        view.document.deleteLater()

    def _on_current_document_changed(self, _index: int) -> None:
        doc = self.current_document()
        self.undo_group.setActiveStack(doc.undo_stack if doc else None)
        self.panels["swatches"].set_document(doc)
        self.center.setCurrentIndex(0 if doc else 1)
        self._refresh_document_ui()

    def _on_document_edited(self, view: DocumentView, *_args) -> None:
        index = self.doc_tabs.indexOf(view)
        if index < 0:
            return
        doc = view.document
        star = "*" if doc.is_modified else ""
        self.doc_tabs.setTabText(index, f"{doc.palette.name}{star} @ {round(view.zoom * 100)}%")
        if view is self.current_view():
            self._refresh_document_ui()

    def _refresh_document_ui(self) -> None:
        doc = self.current_document()
        view = self.current_view()
        has_doc = doc is not None
        has_selection = has_doc and doc.selected >= 0
        for key in ("close", "add_fg", "rename_palette", "zoom_in", "zoom_out", "fit", "actual_size"):
            self.actions[key].setEnabled(has_doc)
        for key in ("delete_swatch", "replace_swatch", "swatch_to_fg"):
            self.actions[key].setEnabled(has_selection)
        self.setWindowTitle(f"{doc.palette.name} — Colorize" if has_doc else "Colorize")
        self.zoom_label.setText(f"{round(view.zoom * 100)}%" if view else "")
        if has_doc:
            n = len(doc.palette)
            text = f"{n} swatch" + ("" if n == 1 else "es")
            if has_selection:
                text += f"  ·  selected {doc.palette.color(doc.selected)}"
            self.info_label.setText(text)
        else:
            self.info_label.setText("")

    def _with_view(self, method: str) -> None:
        view = self.current_view()
        if view:
            getattr(view, method)()

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

    def _choose_foreground(self) -> None:
        color = pick_color(self, self.state.foreground, "Foreground Color")
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
            previous = area
        for panel, dock in self.docks.items():
            if panel not in placed:
                dock.toggleView(False)
        self._workspace = key
        self._rebuild_workspace_menu()
        self._after_layout_change()
        QTimer.singleShot(0, self._apply_panel_width)

    def _apply_panel_width(self) -> None:
        area = self.central_dock.dockAreaWidget()
        sizes = self.dock_manager.splitterSizes(area)
        if len(sizes) == 2 and sum(sizes) > PANEL_WIDTH * 2:
            self.dock_manager.setSplitterSizes(area, [sum(sizes) - PANEL_WIDTH, PANEL_WIDTH])

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

    def _update_status(self) -> None:
        fg = self.state.foreground
        self.fg_chip.set_color(fg)
        self.fg_label.setText(f"{fg}  ·  {format_oklch(fg)}")

    def show_preferences(self) -> None:
        PreferencesDialog(self.theme, self).exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Colorize",
            f"<b>Colorize</b> {__version__}<br>Offline color manager.<br><br>"
            "Interface font: Source Sans 3 (SIL Open Font License).",
        )

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
        self.save_settings()
        QApplication.instance().removeEventFilter(self)
        self.dock_manager.deleteLater()
        super().closeEvent(event)
