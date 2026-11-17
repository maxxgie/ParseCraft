"""Tests for the combined Closure Steps + GOTO Steps tab."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QLabel

from core.engine import analyze
from gui.closure_goto_steps_view import ClosureGotoStepsView

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    v = ClosureGotoStepsView()
    v.update_from(analyze(GRAMMAR, "SLR(1)"))
    yield v
    v.deleteLater()


def test_combined_view_has_two_tables(app, view):
    assert view.closure.table.rowCount() > 0
    assert view.goto.table.rowCount() > 0
    assert view.closure.table is not view.goto.table


def test_closure_headers(view):
    headers = [
        view.closure.table.horizontalHeaderItem(c).text()
        for c in range(view.closure.table.columnCount())
    ]
    assert headers == ["Phase", "Origin Item", "Added Item", "Trigger (• symbol)"]


def test_goto_headers(view):
    headers = [
        view.goto.table.horizontalHeaderItem(c).text()
        for c in range(view.goto.table.columnCount())
    ]
    assert headers == ["Phase", "Item", "Dot-Advanced / Added", "Trigger (• symbol)"]


def test_section_labels_present(view):
    labels = [
        lbl.text()
        for lbl in view.findChildren(QLabel)
        if lbl.text() in ("Closure Steps", "GOTO Steps", "Used Grammar")
    ]
    assert "Closure Steps" in labels
    assert "GOTO Steps" in labels


def test_single_shared_grammar_pane(view):
    # One shared grammar on the right; the embedded views' panes are hidden.
    assert view.grammar.isVisibleTo(view)
    assert not view.closure.grammar.isVisibleTo(view)
    assert not view.goto.grammar.isVisibleTo(view)


def test_tables_side_by_side_with_grammar_right(app, view):
    from PyQt6.QtCore import QPoint

    view.resize(1200, 600)
    view.show()
    app.processEvents()
    c = view.closure.table.mapToGlobal(QPoint(0, 0))
    g = view.goto.table.mapToGlobal(QPoint(0, 0))
    gr = view.grammar.mapToGlobal(QPoint(0, 0))
    assert g.x() > c.x() + 100, "GOTO table must be to the right of closure"
    assert gr.x() > g.x(), "grammar must be the rightmost column"
    assert abs(c.y() - g.y()) < 40, "tables must share a row (aligned tops)"


def test_clear_resets_everything(app, view):
    view.clear()
    assert view.closure.table.rowCount() == 0
    assert view.goto.table.rowCount() == 0