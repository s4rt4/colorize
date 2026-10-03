import random

import numpy as np
import pytest

from colorize.core.books import BookColor, ColorBook, css_named_book, delta_e_2000_many
from colorize.core.delta_e import delta_e_2000, hex_to_lab
from colorize.formats import import_named_colors
from colorize.formats.swatch_files import write_ase
from colorize.storage.library import Library


def test_vectorized_matches_scalar():
    rng = random.Random(3)
    hexes = ["#{:02X}{:02X}{:02X}".format(*(rng.randrange(256) for _ in range(3))) for _ in range(300)]
    labs = np.array([hex_to_lab(h) for h in hexes])
    query = hex_to_lab("#3D6A9E")
    vector = delta_e_2000_many(query, labs)
    for lab, value in zip(labs, vector):
        assert value == pytest.approx(delta_e_2000(query, tuple(lab)), abs=1e-9)


def test_css_book():
    book = css_named_book()
    assert len(book.colors) == 148  # 'transparent' excluded
    names = {c.name: c.hex for c in book.colors}
    assert names["rebeccapurple"] == "#663399"
    best = book.nearest("#FF6347", 3)  # tomato itself
    assert best[0].color.name == "tomato" and best[0].delta_e == 0
    assert best[1].delta_e >= best[0].delta_e


def test_nearest_ranks_by_delta_e():
    book = ColorBook(1, "Test", [BookColor("A", "#FF0000"), BookColor("B", "#EE1111"), BookColor("C", "#0000FF")])
    matches = book.nearest("#F00505", 3)
    expected = sorted(book.colors, key=lambda c: delta_e_2000(hex_to_lab("#F00505"), hex_to_lab(c.hex)))
    assert [m.color for m in matches] == expected
    assert [m.color.name for m in matches] == ["B", "A", "C"]  # #EE1111 looks closer than pure red
    assert ColorBook(2, "Empty", []).nearest("#FFFFFF") == []


def test_named_import_keeps_names(tmp_path):
    ase = tmp_path / "Spot.ase"
    ase.write_bytes(write_ase("Spot Colors", ["#CC0000", "#0055AA"]))
    name, entries = import_named_colors(ase)
    assert name == "Spot Colors" and entries == [("#CC0000", "#CC0000"), ("#0055AA", "#0055AA")]
    gpl = tmp_path / "ral.gpl"
    gpl.write_text("GIMP Palette\nName: RAL sample\n204 0 0\tSignal red\n0 85 170\n", encoding="utf-8")
    assert import_named_colors(gpl) == ("RAL sample", [("Signal red", "#CC0000"), ("#0055AA", "#0055AA")])


def test_books_in_the_library(tmp_path):
    library = Library(tmp_path / "lib.sqlite")
    book_id = library.add_book("My Spot Colors", [("Red 1", "#cc0000"), ("Blue 2", "#0055aa")], source="spot.ase")
    assert library.books() == [(book_id, "My Spot Colors", 2)]
    assert library.book_colors(book_id) == [("Red 1", "#CC0000"), ("Blue 2", "#0055AA")]
    library.delete_book(book_id)
    assert library.books() == [] and library._db.execute("SELECT COUNT(*) FROM book_colors").fetchone()[0] == 0
    library.close()
