"""Tests for the combined LR Items + State Transitions tab."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QLabel

from core.engine import analyze
from gui.lr_items_transitions_view import LRItemsTransitionsView

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    v = LRItemsTransitionsView()
    v.update_from(analyze(GRAMMAR, "SLR(1)"))
    yield v
    v.deleteLater()


def test_combined_view_has_two_tables(app, view):
    assert view.lr_items.table.rowCount() > 0
    assert view.transitions.table.rowCount() > 0
    assert view.lr_items.table is not view.transitions.table


def test_lr_items_headers(view):
    headers = [
        view.lr_items.table.horizontalHeaderItem(c).text()
        for c in range(view.lr_items.table.columnCount())
    ]
    assert headers == ["State", "Production #", "LR Item"]


def test_transition_headers(view):
    headers = [
        view.transitions.table.horizontalHeaderItem(c).text()
        for c in range(view.transitions.table.columnCount())
    ]
    assert headers == ["State", "Configuration State", "Consume", "Next State"]


def test_section_labels_present(view):
    labels = [
        lbl.text()
        for lbl in view.findChildren(QLabel)
        if lbl.text() in ("LR Items", "State Transitions")
    ]
    assert "LR Items" in labels
    assert "State Transitions" in labels


def test_single_shared_grammar_pane(view):
    # A single shared grammar reference is shown; the embedded views' own
    # grammar panes are hidden so the two tables align side by side.
    assert view.grammar.isVisibleTo(view)
    assert not view.lr_items.grammar.isVisibleTo(view)
    assert not view.transitions.grammar.isVisibleTo(view)


def test_tables_are_side_by_side(app, view):
    # The two tables share a row: their top edges line up and the transitions
    # table sits to the right of the LR items table.
    from PyQt6.QtCore import QPoint

    view.resize(1200, 600)
    view.show()
    app.processEvents()
    a = view.lr_items.table.mapToGlobal(QPoint(0, 0))
    b = view.transitions.table.mapToGlobal(QPoint(0, 0))
    assert b.x() > a.x() + 100, "transitions table must be to the right"
    assert abs(a.y() - b.y()) < 40, "tables must share a row (aligned tops)"


def test_clear_resets_both(app, view):
    view.clear()
    assert view.lr_items.table.rowCount() == 0
    assert view.transitions.table.rowCount() == 0