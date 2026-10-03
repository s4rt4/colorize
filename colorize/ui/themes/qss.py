"""Stylesheet generated from theme tokens. No widget hardcodes a color.

``$icons`` points at the per-theme folder of recolored SVGs (see ThemeManager):
``name.svg`` uses ``text``, ``name-muted.svg`` uses ``text_muted``,
``name-disabled.svg`` uses ``text_disabled``, ``name-on-accent.svg`` uses ``accent_text``.
"""

from string import Template

_QSS = Template(r"""
/* ---------- Window chrome ---------- */
QMainWindow, QDialog { background: $bg_panel; }
QMainWindow::separator { background: $bg_app; width: 1px; height: 1px; }

QToolTip {
    background: $bg_header; color: $text;
    border: 1px solid $border_input; padding: 3px 6px;
}

QMenuBar { background: $bg_header; border-bottom: 1px solid $border; padding: 1px 2px; }
QMenuBar::item { background: transparent; padding: 4px 9px; }
QMenuBar::item:selected { background: $bg_hover; }
QMenuBar::item:pressed { background: $bg_selected; }

QMenu { background: $bg_panel; border: 1px solid $border; padding: 4px 0; }
QMenu::item { padding: 4px 28px 4px 26px; background: transparent; }
QMenu::item:selected { background: $accent; color: $accent_text; }
QMenu::item:disabled { color: $text_disabled; }
QMenu::separator { height: 1px; background: $border_input; margin: 4px 0; }
QMenu::indicator { width: 12px; height: 12px; left: 8px; }
QMenu::indicator:checked { image: url($icons/check.svg); }
QMenu::indicator:checked:selected { image: url($icons/check-on-accent.svg); }
QMenu::right-arrow { image: url($icons/chevron-right-muted.svg); width: 10px; height: 10px; right: 8px; }
QMenu::right-arrow:selected { image: url($icons/chevron-right-on-accent.svg); }

/* ---------- Tool and options bars ---------- */
QToolBar { background: $bg_panel; border: none; spacing: 2px; padding: 2px; }
QToolBar#options { border-bottom: 1px solid $border; padding: 3px 6px; }
QToolBar#tools { border-right: 1px solid $border; padding: 6px 3px; }
QToolBar::separator { background: $border_input; width: 1px; height: 1px; margin: 5px 4px; }

QToolButton {
    background: transparent; border: 1px solid transparent;
    border-radius: 3px; padding: 3px;
}
QToolButton:hover { background: $bg_hover; }
QToolButton:pressed, QToolButton:checked { background: $bg_selected; }
QToolButton::menu-indicator { image: none; }

/* ---------- Buttons and inputs ---------- */
QPushButton {
    background: $bg_hover; color: $text;
    border: 1px solid $border_input; border-radius: 3px;
    padding: 4px 14px; min-height: 18px;
}
QPushButton:hover { background: $bg_selected; }
QPushButton:pressed { background: $bg_header; }
QPushButton:disabled { color: $text_disabled; }
QPushButton:default, QPushButton[accent="true"] {
    background: $accent; color: $accent_text; border-color: $accent;
}
QPushButton:default:hover, QPushButton[accent="true"]:hover { background: $accent_hover; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: $bg_input; color: $text;
    border: 1px solid $border_input; border-radius: 2px;
    padding: 2px 5px; min-height: 18px;
    selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border-color: $accent; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: $text_disabled;
}

QComboBox::drop-down { border: none; width: 18px; }
QComboBox::down-arrow { image: url($icons/chevron-down-muted.svg); width: 9px; height: 9px; }
QComboBox::down-arrow:disabled { image: url($icons/chevron-down-disabled.svg); }
QComboBox QAbstractItemView {
    background: $bg_panel; border: 1px solid $border; outline: 0;
    selection-background-color: $accent; selection-color: $accent_text;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    border: none; background: transparent; width: 14px;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url($icons/chevron-up-muted.svg); width: 8px; height: 8px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url($icons/chevron-down-muted.svg); width: 8px; height: 8px; }
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled { image: url($icons/chevron-up-disabled.svg); }
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled { image: url($icons/chevron-down-disabled.svg); }

QCheckBox, QRadioButton { spacing: 6px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 12px; height: 12px;
    border: 1px solid $border_input; background: $bg_input;
}
QCheckBox::indicator { border-radius: 2px; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:checked {
    background: $accent; border-color: $accent; image: url($icons/check-on-accent.svg);
}
QRadioButton::indicator:checked {
    border-color: $accent;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 $accent_text, stop:0.38 $accent_text, stop:0.48 $accent, stop:1 $accent);
}

QSlider::groove:horizontal { height: 2px; background: $border_input; }
QSlider::handle:horizontal {
    width: 10px; height: 10px; margin: -5px 0; border-radius: 6px;
    background: $text; border: 1px solid $border;
}
QSlider::handle:horizontal:disabled { background: $text_disabled; }

QGroupBox { border: 1px solid $border_input; border-radius: 3px; margin-top: 12px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: $text_muted; }

/* ---------- Lists, history, scrolling ---------- */
QListView, QListWidget, QTreeView, QUndoView {
    background: $bg_panel; border: none; outline: 0;
}
QListView::item, QListWidget::item, QUndoView::item { padding: 4px 8px; }
QListView::item:hover, QListWidget::item:hover { background: $bg_hover; }
QListView::item:selected, QListWidget::item:selected {
    background: $bg_selected; color: $text;
}

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll_handle; min-height: 28px; border-radius: 3px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scroll_handle; min-width: 28px; border-radius: 3px; margin: 2px; }
QScrollBar::handle:hover { background: $text_muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ---------- Document tabs ---------- */
QTabWidget#documents::pane { border: none; }
QTabWidget#documents > QTabBar { background: $bg_header; }
QTabBar::tab {
    background: $bg_header; color: $text_muted;
    border: none; border-right: 1px solid $border;
    padding: 5px 10px; min-width: 90px;
}
QTabBar::tab:selected { background: $bg_panel; color: $text; }
QTabBar::tab:hover:!selected { background: $bg_hover; }
QTabBar::close-button { image: url($icons/close-muted.svg); subcontrol-position: right; padding: 2px; }
QTabBar::close-button:hover { image: url($icons/close.svg); background: $bg_hover; border-radius: 2px; }

#canvas, #home { background: $bg_app; }

/* ---------- Status bar ---------- */
QStatusBar { background: $bg_header; color: $text_muted; border-top: 1px solid $border; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $text_muted; padding: 0 6px; }

/* ---------- App-specific roles ---------- */
QLabel[role="muted"] { color: $text_muted; }
QLabel[role="heading"] { font-weight: 600; }
QLabel[role="title"] { font-size: 22px; font-weight: 300; color: $text; }
QLabel[role="badge"] {
    color: $text_muted; border: 1px solid $border_input; border-radius: 3px;
    padding: 0 5px; font-size: 11px;
}
QLabel[role="pass"] { color: $success; font-weight: 600; }
QLabel[role="fail"] { color: $danger; font-weight: 600; }
QLabel[role="metric"] { font-size: 26px; font-weight: 300; color: $text; }
#panelFooter { border-top: 1px solid $border; }
#panelFooter QToolButton { padding: 2px; }

/* ---------- Dock panels (Qt Advanced Docking System) ---------- */
ads--CDockContainerWidget { background: $bg_app; }
ads--CDockSplitter::handle { background: $bg_app; }
ads--CDockSplitter::handle:horizontal { width: 2px; }
ads--CDockSplitter::handle:vertical { height: 2px; }
ads--CDockAreaWidget { background: $bg_panel; }
ads--CDockAreaTitleBar { background: $bg_header; border-bottom: 1px solid $border; }
ads--CDockWidget { background: $bg_panel; border: none; }
QScrollArea#dockWidgetScrollArea { padding: 0; border: none; }

ads--CDockWidgetTab {
    background: $bg_header; border: none; border-right: 1px solid $border;
    padding: 0 4px;
}
ads--CDockWidgetTab[activeTab="true"] { background: $bg_panel; }
ads--CDockWidgetTab QLabel { color: $text_muted; background: transparent; }
ads--CDockWidgetTab[activeTab="true"] QLabel { color: $text; }
ads--CDockWidgetTab:hover QLabel { color: $text; }

ads--CTitleBarButton { background: transparent; border: none; border-radius: 2px; padding: 2px; }
ads--CTitleBarButton:hover { background: $bg_hover; }
#tabsMenuButton::menu-indicator { image: none; }
#tabsMenuButton { qproperty-icon: url($icons/menu-muted.svg); qproperty-iconSize: 14px; }
#detachGroupButton { qproperty-icon: url($icons/undock-muted.svg); qproperty-iconSize: 14px; }
#dockAreaCloseButton { qproperty-icon: url($icons/close-muted.svg); qproperty-iconSize: 12px; }
#dockAreaAutoHideButton { qproperty-icon: url($icons/collapse-muted.svg); qproperty-iconSize: 14px; }
#dockAreaMinimizeButton { qproperty-icon: url($icons/minimize-muted.svg); qproperty-iconSize: 14px; }
#tabCloseButton {
    background: none; border: none; margin-top: 1px; padding: 0;
    qproperty-icon: url($icons/close-muted.svg); qproperty-iconSize: 10px;
}
#tabCloseButton:hover { background: $bg_hover; }

/* Collapsed-to-icons panels (auto-hide side bar) */
ads--CAutoHideSideBar { background: $bg_panel; border: none; qproperty-spacing: 2; }
ads--CAutoHideSideBar[sideBarLocation="2"] { border-left: 1px solid $border; }
ads--CAutoHideSideBar[sideBarLocation="0"] { border-right: 1px solid $border; }
#sideTabsContainerWidget { background: transparent; }
ads--CAutoHideTab {
    qproperty-iconSize: 18px 18px;
    background: transparent; border: none; border-radius: 3px;
    padding: 5px; min-height: 22px; min-width: 22px;
}
ads--CAutoHideTab:hover { background: $bg_hover; }
ads--CAutoHideTab[activeTab="true"] { background: $bg_selected; }
ads--CAutoHideDockContainer { background: $bg_panel; border: 1px solid $border; }
ads--CAutoHideDockContainer ads--CDockAreaTitleBar { background: $bg_header; border: none; padding: 0; }
ads--CAutoHideDockContainer ads--CDockAreaWidget[focused="true"] ads--CDockAreaTitleBar {
    background: $bg_header; border: none; padding: 0;
}
ads--CAutoHideDockContainer #dockAreaAutoHideButton { qproperty-icon: url($icons/expand-muted.svg); }
#autoHideTitleLabel { color: $text; padding-left: 6px; background: transparent; }
ads--CResizeHandle { background: $bg_app; }
""")


def build_qss(tokens: dict[str, str], icon_dir: str) -> str:
    return _QSS.substitute(tokens, icons=icon_dir)
