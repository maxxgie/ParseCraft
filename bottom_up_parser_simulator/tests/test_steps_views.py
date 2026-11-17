"""Tests for the table-based Closure Steps and GOTO Steps views."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from core.engine import analyze
from gui.closure_steps_view import ClosureStepsView
from gui.goto_steps_view import GotoStepsView

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def analysis():
    return analyze(GRAMMAR, "SLR(1)")


def test_closure_view_is_a_table(app, analysis):
    v = ClosureStepsView()
    v.update_from(analysis)
    assert v.table.columnCount() == 4
    headers = [v.table.horizontalHeaderItem(c).text() for c in range(4)]
    assert headers == ["Phase", "Origin Item", "Added Item", "Trigger (• symbol)"]
    assert v.table.rowCount() > 0
    v.deleteLater()


def test_closure_view_has_kernel_and_final_rows(app, analysis):
    v = ClosureStepsView()
    v.update_from(analysis)
    phases = {
        v.table.item(r, 0).text() for r in range(v.table.rowCount())
    }
    assert "Kernel" in phases
    assert "Final" in phases
    # The start state must have at least one closure addition step.
    assert any(p.startswith("Step") for p in phases)
    v.deleteLater()


def test_closure_view_state_switch_repopulates(app, analysis):
    v = ClosureStepsView()
    v.update_from(analysis)
    if v.state_combo.count() > 1:
        v.state_combo.setCurrentIndex(1)
        app.processEvents()
        # Selecting a state rebuilds the table (row count reflects that state).
        assert v.table.rowCount() > 0
        assert v.table.item(0, 0).text() == "Kernel"
    v.deleteLater()


def test_goto_view_is_a_table(app, analysis):
    v = GotoStepsView()
    v.update_from(analysis)
    assert v.table.columnCount() == 4
    headers = [v.table.horizontalHeaderItem(c).text() for c in range(4)]
    assert headers == ["Phase", "Item", "Dot-Advanced / Added", "Trigger (• symbol)"]
    assert v.table.rowCount() > 0
    # Header reports the target state.
    assert "GOTO(I0," in v.header.text()
    v.deleteLater()


def test_goto_view_has_phase_rows(app, analysis):
    v = GotoStepsView()
    v.update_from(analysis)
    phases = {v.table.item(r, 0).text() for r in range(v.table.rowCount())}
    assert "Before" in phases
    assert "Dot moved" in phases
    assert "Result" in phases
    v.deleteLater()


def test_goto_view_symbol_switch_updates(app, analysis):
    v = GotoStepsView()
    v.update_from(analysis)
    if v.symbol_combo.count() > 1:
        first_header = v.header.text()
        v.symbol_combo.setCurrentIndex(1)
        app.processEvents()
        assert v.header.text() != first_header
        assert v.table.rowCount() > 0
    v.deleteLater()


def test_views_clear_resets_tables(app, analysis):
    cv = ClosureStepsView()
    gv = GotoStepsView()
    cv.update_from(analysis)
    gv.update_from(analysis)
    cv.clear()
    gv.clear()
    assert cv.table.rowCount() == 0
    assert gv.table.rowCount() == 0
    cv.deleteLater()
    gv.deleteLater()