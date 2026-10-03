"""SQLite store: the palette library (like Adobe's Libraries panel) and recent files.

Palette documents still save as portable JSON files; the library is the app's own
collection. Schema changes go through MIGRATIONS, keyed by ``PRAGMA user_version``,
so an older library file is upgraded in place when the app opens it.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from colorize.core.color import hex_to_rgb, linear_srgb_to_oklab, normalize_hex, srgb_to_linear

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
    # v2: tags
    """
    CREATE TABLE palette_tags (
        palette_id INTEGER NOT NULL REFERENCES palettes(id) ON DELETE CASCADE,
        tag TEXT NOT NULL COLLATE NOCASE,
        PRIMARY KEY (palette_id, tag)
    );
    CREATE INDEX palette_tags_tag ON palette_tags(tag);
    """,
    # v3: color books (named reference colors, imported by the user)
    """
    CREATE TABLE color_books (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        added TEXT NOT NULL
    );
    CREATE TABLE book_colors (
        book_id INTEGER NOT NULL REFERENCES color_books(id) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        name TEXT NOT NULL,
        hex TEXT NOT NULL,
        PRIMARY KEY (book_id, position)
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
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimilarPalette:
    palette: LibraryPalette
    distance: float  # OKLab distance of its closest color to the query (x100 reads like ΔE)
    closest: str  # that color


def normalize_tags(tags) -> list[str]:
    """Trim, drop empties and case-insensitive duplicates, keep first spelling and order."""
    seen, result = set(), []
    for tag in tags:
        tag = " ".join(str(tag).split())
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            result.append(tag)
    return result


def _oklab(hex_color: str) -> tuple[float, float, float]:
    return linear_srgb_to_oklab(*(srgb_to_linear(c / 255) for c in hex_to_rgb(hex_color)))


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

    def add_palette(self, name: str, colors, tags=()) -> int:
        colors = [normalize_hex(c) for c in colors]
        stamp = _now()
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO palettes (name, created, updated) VALUES (?, ?, ?)", (name, stamp, stamp)
            )
            palette_id = cursor.lastrowid
            self._write_colors(palette_id, colors)
            self._write_tags(palette_id, tags)
        return palette_id

    # ----- tags -----

    def set_tags(self, palette_id: int, tags) -> None:
        with self._db:
            self._db.execute("DELETE FROM palette_tags WHERE palette_id = ?", (palette_id,))
            self._write_tags(palette_id, tags)

    def _write_tags(self, palette_id: int, tags) -> None:
        self._db.executemany(
            "INSERT INTO palette_tags (palette_id, tag) VALUES (?, ?)",
            [(palette_id, tag) for tag in normalize_tags(tags)],
        )

    def all_tags(self) -> list[tuple[str, int]]:
        """(tag, number of palettes), most used first."""
        rows = self._db.execute(
            "SELECT MIN(tag), COUNT(*) FROM palette_tags GROUP BY tag ORDER BY COUNT(*) DESC, MIN(tag) COLLATE NOCASE"
        )
        return [(tag, count) for tag, count in rows]

    # ----- similar colors -----

    def similar_palettes(self, color: str, limit: int = 50, max_distance: float = 0.12) -> list[SimilarPalette]:
        """Palettes holding a color close to ``color`` (OKLab distance), closest first."""
        target = _oklab(normalize_hex(color))
        best: dict[int, tuple[float, str]] = {}
        for palette_id, hex_color in self._db.execute("SELECT palette_id, hex FROM palette_colors"):
            lab = _oklab(hex_color)
            distance = sum((x - y) ** 2 for x, y in zip(lab, target)) ** 0.5
            if distance <= max_distance and (palette_id not in best or distance < best[palette_id][0]):
                best[palette_id] = (distance, hex_color)
        ranked = sorted(best.items(), key=lambda item: (item[1][0], -item[0]))[:limit]
        return [SimilarPalette(self.get_palette(pid), distance, hex_color) for pid, (distance, hex_color) in ranked]

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

    def palettes(self, search: str = "", tag: str | None = None) -> list[LibraryPalette]:
        """Newest first; ``search`` matches the name, a tag (case-insensitive) or an exact
        hex; ``tag`` keeps only palettes carrying that tag."""
        query = "SELECT id, name, updated FROM palettes"
        conditions, params = [], []
        if tag:
            conditions.append("id IN (SELECT palette_id FROM palette_tags WHERE tag = ?)")
            params.append(tag)
        if search:
            conditions.append(
                "(name LIKE ? ESCAPE '\\' OR id IN (SELECT palette_id FROM palette_colors WHERE hex = ?)"
                " OR id IN (SELECT palette_id FROM palette_tags WHERE tag LIKE ? ESCAPE '\\'))"
            )
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            hex_match = ""
            try:
                hex_match = normalize_hex(search)
            except ValueError:
                pass
            params += [pattern, hex_match, pattern]
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
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
        tags = tuple(
            tag
            for (tag,) in self._db.execute(
                "SELECT tag FROM palette_tags WHERE palette_id = ? ORDER BY rowid", (palette_id,)
            )
        )
        return LibraryPalette(palette_id, name, colors, updated, tags)

    # ----- color books -----

    def add_book(self, name: str, entries, source: str = "") -> int:
        """``entries``: [(color name, hex)]."""
        rows = [(n, normalize_hex(h)) for n, h in entries]
        with self._db:
            book_id = self._db.execute(
                "INSERT INTO color_books (name, source, added) VALUES (?, ?, ?)", (name, source, _now())
            ).lastrowid
            self._db.executemany(
                "INSERT INTO book_colors (book_id, position, name, hex) VALUES (?, ?, ?, ?)",
                [(book_id, i, n, h) for i, (n, h) in enumerate(rows)],
            )
        return book_id

    def books(self) -> list[tuple[int, str, int]]:
        """(id, name, number of colors), in the order they were added."""
        rows = self._db.execute(
            "SELECT b.id, b.name, COUNT(c.position) FROM color_books b "
            "LEFT JOIN book_colors c ON c.book_id = b.id GROUP BY b.id ORDER BY b.id"
        )
        return [(book_id, name, count) for book_id, name, count in rows]

    def book_colors(self, book_id: int) -> list[tuple[str, str]]:
        rows = self._db.execute("SELECT name, hex FROM book_colors WHERE book_id = ? ORDER BY position", (book_id,))
        return [(name, hex_color) for name, hex_color in rows]

    def delete_book(self, book_id: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM color_books WHERE id = ?", (book_id,))

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
