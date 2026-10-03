import sqlite3

import pytest

from colorize.storage.library import RECENT_LIMIT, SCHEMA_VERSION, Library, LibraryError


@pytest.fixture
def library(tmp_path):
    lib = Library(tmp_path / "library.sqlite")
    yield lib
    lib.close()


def test_new_library_is_at_current_schema(library):
    assert library.schema_version == SCHEMA_VERSION


def test_palette_crud(library):
    pid = library.add_palette("Brand", ["#1f3a5f", "f2c14e"])
    saved = library.get_palette(pid)
    assert saved.name == "Brand" and saved.colors == ("#1F3A5F", "#F2C14E")

    library.update_palette(pid, "Brand v2", ["#000000"])
    assert library.get_palette(pid).colors == ("#000000",)
    library.rename_palette(pid, "Final")
    assert library.get_palette(pid).name == "Final"

    library.delete_palette(pid)
    assert library.get_palette(pid) is None
    rows = library._db.execute("SELECT COUNT(*) FROM palette_colors").fetchone()[0]
    assert rows == 0  # colors cascade with their palette


def test_update_missing_palette_fails(library):
    with pytest.raises(LibraryError):
        library.update_palette(999, "x", [])


def test_list_and_search(library):
    a = library.add_palette("Ocean", ["#0077BE", "#FFFFFF"])
    b = library.add_palette("Forest_50%", ["#228B22"])
    assert [p.id for p in library.palettes()] == [b, a]  # newest first
    assert [p.name for p in library.palettes("oce")] == ["Ocean"]
    assert [p.name for p in library.palettes("#228b22")] == ["Forest_50%"]  # by exact hex
    assert [p.name for p in library.palettes("_50%")] == ["Forest_50%"]  # LIKE wildcards are literal
    assert library.palettes("nothing") == []


def test_persists_across_connections(tmp_path):
    path = tmp_path / "lib.sqlite"
    first = Library(path)
    first.add_palette("Keep", ["#123456"])
    first.close()
    second = Library(path)
    assert [p.name for p in second.palettes()] == ["Keep"]
    second.close()


def test_recent_files_are_capped_and_deduplicated(library, tmp_path):
    paths = [tmp_path / f"p{i}.json" for i in range(RECENT_LIMIT + 3)]
    for path in paths:
        library.add_recent(path)
    library.add_recent(paths[0])  # reopening moves it to the top
    recent = library.recent_files()
    assert len(recent) == RECENT_LIMIT
    assert recent[0] == str(paths[0].resolve())
    library.remove_recent(paths[0])
    assert str(paths[0].resolve()) not in library.recent_files()
    library.clear_recent()
    assert library.recent_files() == []


def test_refuses_a_library_from_a_newer_app(tmp_path):
    path = tmp_path / "future.sqlite"
    db = sqlite3.connect(path)
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    db.close()
    with pytest.raises(LibraryError, match="newer Colorize"):
        Library(path)


def test_migrations_upgrade_an_old_file(tmp_path, monkeypatch):
    """A future migration runs on an existing file and keeps its data."""
    import colorize.storage.library as storage

    path = tmp_path / "old.sqlite"
    old = Library(path)
    pid = old.add_palette("Old", ["#ABCDEF"])
    old.close()

    monkeypatch.setattr(storage, "MIGRATIONS", storage.MIGRATIONS + ("ALTER TABLE palettes ADD COLUMN note TEXT;",))
    monkeypatch.setattr(storage, "SCHEMA_VERSION", len(storage.MIGRATIONS))
    upgraded = storage.Library(path)
    assert upgraded.schema_version == SCHEMA_VERSION + 1
    assert upgraded.get_palette(pid).colors == ("#ABCDEF",)
    upgraded._db.execute("UPDATE palettes SET note = 'ok'")
    upgraded.close()
