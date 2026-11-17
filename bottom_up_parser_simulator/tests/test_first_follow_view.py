"""Tests for the First/Follow sets view presentation."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from core.engine import analyze
from gui.first_follow_view import FirstFollowView, _SetDelegate, _format_set

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    analysis = analyze(GRAMMAR, "SLR(1)")
    v = FirstFollowView()
    v.update_from(analysis)
    yield v
    v.deleteLater()


def test_three_columns_with_expected_headers(view):
    assert view.table.columnCount() == 3
    assert view.table.horizontalHeaderItem(0).text() == "Production / Symbol"
    assert view.table.horizontalHeaderItem(1).text() == "FIRST"
    assert view.table.horizontalHeaderItem(2).text() == "FOLLOW"


def test_format_set_brackets():
    assert _format_set({"a", "b"}) == "{ a, b }"
    assert _format_set(set()) == "{ }"


def test_first_cell_contains_set_brackets(view):
    # FIRST sets are rendered with { ... } brackets.
    for row in range(view.table.rowCount()):
        text = view.table.item(row, 1).text()
        assert text.startswith("{") and text.endswith("}")


def test_delegate_wraps_epsilon(view):
    html = _SetDelegate._html("{ +, ε }")
    assert "#7c3aed" in html  # epsilon accent colour
    assert "ε" in html


def test_delegate_wraps_dollar(view):
    html = _SetDelegate._html("{ $, ) }")
    assert "#b45309" in html  # dollar accent colour
    assert "$" in html


def test_delegate_passes_plain_sets(view):
    html = _SetDelegate._html("{ (, id }")
    # Plain sets get no accent span (no $ amber, no ε violet).
    assert "#b45309" not in html
    assert "#7c3aed" not in html


def test_delegate_always_pins_base_colour(view):
    # Every set is drawn with an explicit dark base colour so the contents stay
    # readable even when the active palette's text colour is light.
    for text in ("{ a, b }", "{ $, ε }", "{ }"):
        html = _SetDelegate._html(text)
        assert "color:#1F2937" in html


def test_detail_panel_shows_derivation(view):
    # Selecting the start symbol must populate the explanation panel with
    # FIRST/FOLLOW derivation rules including the $ EOF marker.
    for row in range(view.table.rowCount()):
        if view.table.item(row, 0).text() == "E":
            view.table.selectRow(row)
            break
    text = view.detail.toPlainText()
    assert "FIRST derivation" in text
    assert "FOLLOW derivation" in text
    assert "$" in text


def test_non_terminal_symbols_are_bold(view):
    # Non-terminal rows use a bold symbol font; terminal rows are not bold.
    for row in range(view.table.rowCount()):
        is_nt = view._rows[row][1]
        bold = view.table.item(row, 0).font().bold()
        assert bold == is_nt


def test_set_cells_visible_under_light_palette(app):
    # Regression: the delegate used to draw with the painter's default pen, so
    # on a palette whose text colour is light the FIRST/FOLLOW contents became
    # invisible. Pinning the base colour must keep dark text on the light fill.
    from PyQt6.QtGui import QColor, QPalette, QPixmap

    original = app.palette()
    light = QPalette(original)
    light.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
    light.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
    app.setPalette(light)
    try:
        analysis = analyze(GRAMMAR, "SLR(1)")
        v = FirstFollowView()
        v.resize(900, 500)
        v.update_from(analysis)
        v.show()
        app.processEvents()
        pm = QPixmap(v.table.size())
        v.table.render(pm)
        img = pm.toImage()

        header = v.table.horizontalHeader()
        row_y = v.table.rowViewportPosition(1)
        dark = 0
        for col in (1, 2):
            x0 = header.sectionViewportPosition(col)
            x1 = x0 + header.sectionSize(col)
            for y in range(row_y + 2, row_y + 22):
                for x in range(x0, x1):
                    c = img.pixelColor(x, y)
                    if c.red() < 120 and c.green() < 120:
                        dark += 1
        assert dark > 0, "FIRST/FOLLOW set text must remain visible"
        v.deleteLater()
    finally:
        app.setPalette(original)