import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from colorize.ui.themes import ThemeManager  # noqa: E402


@pytest.fixture(autouse=True)
def destroy_leftover_widgets(qapp):
    """Delete every top-level widget after each test. Closed-but-alive windows pile up
    otherwise, and each theme change restyles all of them (seconds per test by the end)."""
    yield
    for widget in QApplication.topLevelWidgets():
        if hasattr(widget, "ask_save_changes"):
            widget.ask_save_changes = lambda doc: "discard"
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope="session")
def icon_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("icons")


@pytest.fixture
def theme(qapp, icon_cache):
    manager = ThemeManager(qapp, icon_cache)
    manager.apply("gray")
    return manager


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "settings.ini")


@pytest.fixture
def settings(settings_path):
    return QSettings(settings_path, QSettings.Format.IniFormat)


@pytest.fixture
def window(qtbot, theme, settings):
    from colorize.ui.main_window import MainWindow

    win = MainWindow(theme, settings)
    win.ask_save_changes = lambda doc: "discard"  # never block on the modal prompt
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win
