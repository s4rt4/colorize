from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from colorize.ui.main_window import MainWindow
from colorize.ui.workspaces import WORKSPACES


def open_panels(win):
    return {key for key, dock in win.docks.items() if not dock.isClosed()}


def test_shell_layout(window):
    assert window.tools_bar.isVisible()
    assert window.options_bar.isVisible()
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles == ["File", "Edit", "Color", "Palette", "View", "Window", "Help"]
    assert window.current_document() is not None
    assert open_panels(window) == {p for group in WORKSPACES["essentials"] for p in group}


def test_workspaces_switch_and_reset(window, qtbot):
    window._apply_workspace("accessibility")
    assert open_panels(window) == {"contrast", "cvd", "color", "swatches"}
    window.docks["contrast"].toggleView(False)
    window._reset_workspace()
    assert "contrast" in open_panels(window)
    window._apply_workspace("essentials")
    assert open_panels(window) == {p for group in WORKSPACES["essentials"] for p in group}


def test_custom_workspace_round_trip(window, monkeypatch):
    window._apply_workspace("palette")
    monkeypatch.setattr("PyQt6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("Mine", True))
    window._new_workspace()
    assert "Mine" in window.dock_manager.perspectiveNames()
    window._apply_workspace("essentials")
    window._open_custom_workspace("Mine")
    assert open_panels(window) == {"swatches", "export", "color", "harmony"}
    window._delete_workspace("Mine")
    assert "Mine" not in window.dock_manager.perspectiveNames()


def test_collapse_panels_to_icons_and_back(window):
    before = open_panels(window)
    window.actions["collapse_panels"].trigger()
    assert all(window.docks[p].isAutoHide() for p in before)
    window.actions["collapse_panels"].trigger()
    assert not any(d.isAutoHide() for d in window.docks.values())
    assert open_panels(window) == before


def test_tab_hides_and_restores_everything(window):
    before = open_panels(window)
    window._on_tab_pressed()
    assert window.panels_hidden
    assert open_panels(window) == set()
    assert not window.tools_bar.isVisible()
    window._on_tab_pressed()
    assert open_panels(window) == before
    assert window.tools_bar.isVisible() and window.options_bar.isVisible()


def test_tab_in_text_field_does_not_hide_panels(window, qtbot):
    hex_edit = window.panels["color"].hex_edit
    hex_edit.setFocus()
    qtbot.waitUntil(hex_edit.hasFocus)
    window._on_tab_pressed()
    assert not window.panels_hidden


def test_undo_follows_active_document(window):
    first = window.current_document()
    window.actions["add_fg"].trigger()
    assert len(first.palette) == 9
    second = window.new_document()
    assert window.undo_group.activeStack() is second.undo_stack
    assert not window.undo_action.isEnabled()
    window.doc_tabs.setCurrentIndex(0)
    window.undo_action.trigger()
    assert len(first.palette) == 8
    assert "*" not in window.doc_tabs.tabText(0)


def test_modified_marker_and_zoom_in_tab_title(window):
    window.actions["add_fg"].trigger()
    assert window.doc_tabs.tabText(0) == "Untitled-1* @ 100%"
    window.actions["zoom_in"].trigger()
    assert window.doc_tabs.tabText(0) == "Untitled-1* @ 150%"


def test_selection_drives_actions(window):
    doc = window.current_document()
    doc.select(-1)
    assert not window.actions["delete_swatch"].isEnabled()
    doc.select(2)
    assert window.actions["delete_swatch"].isEnabled()
    window.actions["delete_swatch"].trigger()
    assert len(doc.palette) == 7


def test_closing_last_document_shows_home(window):
    window.close_document()
    assert window.current_document() is None
    assert window.center.currentIndex() == 1
    assert not window.actions["add_fg"].isEnabled()
    window.actions["new"].trigger()
    assert window.center.currentIndex() == 0


def test_tool_shortcuts_and_space_for_hand(window, qtbot):
    window.tool_actions["zoom"].trigger()
    assert window.state.tool == "zoom"
    window.doc_tabs.currentWidget().grid.setFocus()
    QApplication.setActiveWindow(window)
    target = QApplication.focusWidget() or window
    QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier))
    assert window.state.tool == "hand"
    QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier))
    assert window.state.tool == "zoom"


def test_swap_and_default_colors(window):
    window.state.set_foreground("#FF0000")
    window.actions["swap_colors"].trigger()
    assert window.state.background == "#FF0000"
    window.actions["default_colors"].trigger()
    assert window.state.foreground == "#000000"


def test_theme_switch_live(window, theme):
    window.theme_actions["dark"].trigger()
    assert theme.name == "dark"
    assert window.theme_actions["dark"].isChecked()
    assert not window.actions["darker"].isEnabled()
    window.actions["lighter"].trigger()
    window.actions["lighter"].trigger()
    assert theme.name == "light"
    assert not window.actions["lighter"].isEnabled()


def test_drag_reorders_swatches(window, qtbot):
    view = window.current_view()
    grid = view.grid
    doc = window.current_document()
    first = doc.palette.color(0)
    start = grid.cell_rect(0).center()
    end = grid.cell_rect(2).center() + QPoint(grid.cell_rect(2).width() // 2 + 4, 0)
    qtbot.mousePress(grid, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(grid, start + QPoint(10, 0))
    qtbot.mouseMove(grid, end)
    qtbot.mouseRelease(grid, Qt.MouseButton.LeftButton, pos=end)
    assert doc.palette.color(2) == first
    window.undo_action.trigger()
    assert doc.palette.color(0) == first


def test_settings_persist_theme_workspace_and_layout(qtbot, theme, settings, settings_path):
    from PyQt6.QtCore import QSettings

    win = MainWindow(theme, settings)
    win.ask_save_changes = lambda doc: "discard"
    qtbot.addWidget(win)
    win.show()
    theme.apply("light")
    win._apply_workspace("accessibility")
    win.docks["history"].toggleView(True)
    win.close()

    theme.apply("gray")
    reopened_settings = QSettings(settings_path, QSettings.Format.IniFormat)
    assert reopened_settings.value("ui/theme") == "light"
    win2 = MainWindow(theme, reopened_settings)
    win2.ask_save_changes = lambda doc: "discard"
    qtbot.addWidget(win2)
    win2.show()
    assert win2._workspace == "accessibility"
    assert open_panels(win2) == {"contrast", "cvd", "color", "swatches", "history"}
