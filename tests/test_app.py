from pathlib import Path

from colorize.app import Profile, parse_args
from colorize.ui.splash import SplashScreen


def test_parse_args():
    assert parse_args(["colorize"]) == (None, False, [])
    profile, smoke, files = parse_args(["colorize", "a.json", "--profile", "P", "--smoke-test", "b.png"])
    assert profile == Path("P") and smoke and files == ["a.json", "b.png"]


def test_portable_profile_keeps_everything_together(tmp_path, qapp):
    profile = Profile.portable(tmp_path / "portable")
    profile.settings.setValue("ui/theme", "dark")
    profile.settings.sync()
    assert (tmp_path / "portable" / "settings.ini").exists()
    for path in (profile.library, profile.cache, profile.log):
        assert path.is_relative_to(tmp_path / "portable")


def test_splash_paints_status(qapp):
    from colorize.app import LOGO

    splash = SplashScreen(str(LOGO), "9.9.9")
    splash.show()
    splash.show_message("Opening library…")
    assert splash.message == "Opening library…"
    image = splash.grab().toImage()
    assert image.width() >= 620 and not image.isNull()
    splash.close()
