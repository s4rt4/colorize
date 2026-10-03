import pytest

from colorize.ui.library_panel import _DISTANCE_ROLE, _PALETTE_ROLE


@pytest.fixture
def library_panel(window):
    window.docks["library"].setAsCurrentTab()
    lib = window.library
    lib.add_palette("Ocean", ["#0077BE", "#FFFFFF"], tags=["blue", "web"])
    lib.add_palette("Forest", ["#228B22", "#E63A47"], tags=["green", "web"])
    lib.add_palette("Night", ["#111111"], tags=["dark"])
    panel = window.panels["library"]
    panel.refresh()
    return panel


def test_tag_filter(library_panel):
    labels = [library_panel.tag_filter.itemText(i) for i in range(library_panel.tag_filter.count())]
    assert labels[:2] == ["All tags", "web (2)"]
    library_panel.tag_filter.setCurrentIndex(library_panel.tag_filter.findData("web"))
    assert library_panel.list.count() == 2
    library_panel.search.setText("oce")
    assert library_panel.list.count() == 1


def test_similar_to_foreground(window, library_panel):
    window.state.set_foreground("#E63946")
    library_panel.similar.setChecked(True)
    assert library_panel.list.count() == 1
    assert library_panel.selected() is None
    item = library_panel.list.item(0)
    assert item.data(_PALETTE_ROLE).name == "Forest"
    assert item.data(_DISTANCE_ROLE) < 0.01
    window.state.set_foreground("#0078BF")  # follows the foreground live
    assert library_panel.list.item(0).data(_PALETTE_ROLE).name == "Ocean"
    window.state.set_foreground("#7F00FF")
    assert library_panel.list.count() == 0
    assert "No saved palette has a color close" in library_panel.empty.text()


def test_edit_tags(window, library_panel, monkeypatch):
    library_panel.list.setCurrentRow(0)
    target = library_panel.selected()
    monkeypatch.setattr("colorize.ui.library_panel.QInputDialog.getText", lambda *a, **k: ("brand,  Web , brand", True))
    library_panel.edit_tags_selected()
    assert window.library.get_palette(target.id).tags == ("brand", "Web")
