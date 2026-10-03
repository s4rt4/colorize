"""Screen sampling through xdg-desktop-portal (Wayland). The D-Bus round trip itself
needs a Linux desktop; everything around it is checked here with a fake portal."""

from PyQt6.QtCore import QObject, QPointF, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QImage

from colorize.ui.screen_sampler import (
    ScreenSampler,
    needs_portal,
    portal_request_path,
    split_desktop,
)


class FakeScreen:
    def __init__(self, x, y, w, h):
        self._geometry = QRect(x, y, w, h)

    def geometry(self):
        return self._geometry


class FakePortal(QObject):
    done = pyqtSignal(str)
    answer = ""

    def request(self):
        self.done.emit(self.answer)


def desktop(width, height, left="#FF0000", right="#00FF00") -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(left))
    for x in range(width // 2, width):
        for y in range(height):
            image.setPixelColor(x, y, QColor(right))
    return image


def test_portal_only_on_wayland():
    assert needs_portal("linux", {"XDG_SESSION_TYPE": "wayland"})
    assert needs_portal("linux", {"WAYLAND_DISPLAY": "wayland-0"})
    assert not needs_portal("linux", {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"})
    assert not needs_portal("win32", {"WAYLAND_DISPLAY": "wayland-0"})


def test_request_path_follows_the_portal_spec():
    assert portal_request_path(":1.42", "colorize7") == "/org/freedesktop/portal/desktop/request/1_42/colorize7"


def test_split_desktop_two_screens_at_200_percent():
    screens = [FakeScreen(0, 0, 100, 50), FakeScreen(100, 0, 100, 50)]
    parts = split_desktop(desktop(400, 100), screens)
    assert [(p.width(), p.height(), p.devicePixelRatio()) for _, p in parts] == [(200, 100, 2.0), (200, 100, 2.0)]
    assert parts[0][1].toImage().pixelColor(10, 10) == QColor("#FF0000")
    assert parts[1][1].toImage().pixelColor(10, 10) == QColor("#00FF00")


def test_split_desktop_handles_offsets_and_nothing():
    parts = split_desktop(desktop(300, 100), [FakeScreen(-150, 0, 150, 50), FakeScreen(0, 0, 150, 50)])
    assert [p.width() for _, p in parts] == [150, 150]
    assert split_desktop(QImage(), [FakeScreen(0, 0, 10, 10)]) == []


def test_sampler_uses_the_portal_picture(qtbot, tmp_path, monkeypatch):
    screen = QGuiApplication.primaryScreen()
    g = screen.geometry()
    shot = tmp_path / "Screenshot.png"
    desktop(g.width() * 2, g.height() * 2, "#3D6A9E", "#3D6A9E").save(str(shot))
    FakePortal.answer = str(shot)
    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: [screen]))
    sampler = ScreenSampler(portal=FakePortal)
    picked = []
    sampler.picked.connect(picked.append)
    sampler.start()
    assert len(sampler.overlays) == 1 and not shot.exists()  # the portal's file is cleaned up
    overlay = sampler.overlays[0]
    assert overlay.color_at(QPointF(5, 5)) == "#3D6A9E"
    sampler.finish(overlay.color_at(QPointF(5, 5)))
    assert picked == ["#3D6A9E"] and not sampler.active


def test_cancelled_portal_request_finishes_quietly(qtbot):
    FakePortal.answer = ""
    sampler = ScreenSampler(portal=FakePortal)
    finished = []
    sampler.finished.connect(lambda: finished.append(True))
    sampler.start()
    assert finished == [True] and not sampler.active
