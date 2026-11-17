"""Tests for the Canonical Collection (LR states) tab interactions."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.engine import analyze
from gui.lr_states_view import LRStatesView

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    v = LRStatesView()
    v.resize(1000, 600)
    v.update_from(analyze(GRAMMAR, "SLR(1)"))
    v.show()
    app.processEvents()
    yield v
    v.deleteLater()


def _click(view, row, col):
    table = view.table
    rect = table.visualItemRect(table.item(row, col))
    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(rect.center().x(), rect.center().y()),
    )


def test_every_row_is_clickable(view):
    # Regression: clicking any row must select that row.  (With SingleSelection
    # plus a selectRow loop, only the last row of each state group stayed
    # selected, so most rows appeared unclickable.)
    table = view.table
    assert table.rowCount() > 0
    for row in range(table.rowCount()):
        _click(view, row, 2)
        selected = {idx.row() for idx in table.selectedIndexes()}
        assert row in selected, f"row {row} did not respond to a click"


def test_click_selects_whole_state_group(view):
    # Clicking a row highlights the entire state group (all its items).
    table = view.table
    # Pick a state that has more than one item.
    target_state = None
    for row in range(table.rowCount()):
        state_id = view._item_rows[row].state_id
        group = [
            r
            for r in range(table.rowCount())
            if view._item_rows[r].state_id == state_id
        ]
        if len(group) > 1:
            target_state = state_id
            break
    assert target_state is not None, "expected a multi-item state"
    group = {
        r
        for r in range(table.rowCount())
        if view._item_rows[r].state_id == target_state
    }
    _click(view, min(group), 2)
    selected = {idx.row() for idx in table.selectedIndexes()}
    assert selected == group


def test_click_updates_detail_panel(view):
    table = view.table
    for row in range(table.rowCount()):
        state_id = view._item_rows[row].state_id
        _click(view, row, 2)
        assert f"STATE {state_id}" in view.detail.toPlainText()
        break


def test_click_state_column_selects_group(view):
    # The State column is a spanned cell; clicking it must still select.
    table = view.table
    _click(view, 0, 0)
    selected = {idx.row() for idx in table.selectedIndexes()}
    assert 0 in selected