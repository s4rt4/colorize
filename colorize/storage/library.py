"""SQLite store: the palette library (like Adobe's Libraries panel) and recent files.

Palette documents still save as portable JSON files; the library is the app's own
collection. Schema changes go through MIGRATIONS, keyed by ``PRAGMA user_version``,
so an older library file is upgraded in place when the app opens it.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from colorize.core.color import normalize_hex

RECENT_LIMIT = 10

# Each entry upgrades the schema from version i to i + 1. Never edit a shipped entry.
MIGRATIONS = (
    """
    CREATE TABLE palettes (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        created TEXT NOT NULL,
        updated TEXT NOT NULL
    );
    CREATE TABLE palette_colors (
        palette_id INTEGER NOT NULL REFERENCES palettes(id) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        hex TEXT NOT NULL,
        PRIMARY KEY (palette_id, position)
    );
    CREATE INDEX palette_colors_hex ON palette_colors(hex);
    CREATE TABLE recent_files (
        path TEXT PRIMARY KEY,
        opened TEXT NOT NULL
    );
    """,
)
SCHEMA_VERSION = len(MIGRATIONS)


@dataclass(frozen=True)
class LibraryPalette:
    id: int
    name: str
    colors: tuple[str, ...]
    updated: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LibraryError(RuntimeError):
    pass


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    @property
    def schema_version(self) -> int:
        return self._db.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        version = self.schema_version
        if version > SCHEMA_VERSION:
            raise LibraryError(
                f"{self.path.name} was written by a newer Colorize (schema {version}, this app knows {SCHEMA_VERSION})"
            )
        for target in range(version + 1, SCHEMA_VERSION + 1):
            with self._db:  # one transaction per step: a failed step leaves the previous version intact
                self._db.executescript(f"BEGIN; {MIGRATIONS[target - 1]} PRAGMA user_version = {target}; COMMIT;")

    # ----- palettes -----

    def add_palette(self, name: str, colors) -> int:
        colors = [normalize_hex(c) for c in colors]
        stamp = _now()
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO palettes (name, created, updated) VALUES (?, ?, ?)", (name, stamp, stamp)
            )
            palette_id = cursor.lastrowid
            self._write_colors(palette_id, colors)
        return palette_id

    def update_palette(self, palette_id: int, name: str, colors) -> None:
        colors = [normalize_hex(c) for c in colors]
        with self._db:
            changed = self._db.execute(
                "UPDATE palettes SET name = ?, updated = ? WHERE id = ?", (name, _now(), palette_id)
            ).rowcount
            if not changed:
                raise LibraryError(f"no palette with id {palette_id}")
            self._db.execute("DELETE FROM palette_colors WHERE palette_id = ?", (palette_id,))
            self._write_colors(palette_id, colors)

    def rename_palette(self, palette_id: int, name: str) -> None:
        with self._db:
            self._db.execute("UPDATE palettes SET name = ?, updated = ? WHERE id = ?", (name, _now(), palette_id))

    def delete_palette(self, palette_id: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM palettes WHERE id = ?", (palette_id,))

    def _write_colors(self, palette_id: int, colors) -> None:
        self._db.executemany(
            "INSERT INTO palette_colors (palette_id, position, hex) VALUES (?, ?, ?)",
            [(palette_id, i, c) for i, c in enumerate(colors)],
        )

    def get_palette(self, palette_id: int) -> LibraryPalette | None:
        row = self._db.execute("SELECT id, name, updated FROM palettes WHERE id = ?", (palette_id,)).fetchone()
        return self._palette(row) if row else None

    def palettes(self, search: str = "") -> list[LibraryPalette]:
        """Newest first; ``search`` matches the name (case-insensitive) or an exact hex."""
        query = "SELECT id, name, updated FROM palettes"
        params: tuple = ()
        if search:
            query += (
                " WHERE name LIKE ? ESCAPE '\\' OR id IN (SELECT palette_id FROM palette_colors WHERE hex = ?)"
            )
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            hex_match = ""
            try:
                hex_match = normalize_hex(search)
            except ValueError:
                pass
            params = (pattern, hex_match)
        query += " ORDER BY updated DESC, id DESC"
        return [self._palette(row) for row in self._db.execute(query, params).fetchall()]

    def _palette(self, row) -> LibraryPalette:
        palette_id, name, updated = row
        colors = tuple(
            hex_color
            for (hex_color,) in self._db.execute(
                "SELECT hex FROM palette_colors WHERE palette_id = ? ORDER BY position", (palette_id,)
            )
        )
        return LibraryPalette(palette_id, name, colors, updated)

    # ----- recent files -----

    def add_recent(self, path) -> None:
        path = str(Path(path).resolve())
        with self._db:
            self._db.execute(
                "INSERT INTO recent_files (path, opened) VALUES (?, ?) ON CONFLICT(path) DO UPDATE SET opened = excluded.opened",
                (path, _now()),
            )
            self._db.execute(
                "DELETE FROM recent_files WHERE path NOT IN "
                "(SELECT path FROM recent_files ORDER BY opened DESC, rowid DESC LIMIT ?)",
                (RECENT_LIMIT,),
            )

    def recent_files(self) -> list[str]:
        rows = self._db.execute("SELECT path FROM recent_files ORDER BY opened DESC, rowid DESC").fetchall()
        return [path for (path,) in rows]

    def remove_recent(self, path) -> None:
        with self._db:
            self._db.execute("DELETE FROM recent_files WHERE path = ?", (str(Path(path).resolve()),))

    def clear_recent(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM recent_files")
