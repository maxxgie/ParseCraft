"""Tests for ACTION/GOTO cell explanations."""

from __future__ import annotations

from core.engine import analyze
from core.table_explain import explain_action, explain_goto

EXPRESSION = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def test_explain_shift_action():
    result = analyze(EXPRESSION, "SLR(1)")
    text = explain_action(result, 0, "id")
    assert "SHIFT" in text
    assert "GOTO(I0, id)" in text
    assert "immediately after the dot" in text


def test_explain_reduce_action():
    result = analyze(EXPRESSION, "SLR(1)")
    for (state, terminal), action in result.table.action.items():
        if action.action_type == "reduce":
            text = explain_action(result, state, terminal)
            assert "REDUCE" in text
            assert "completed item" in text
            assert "Lookahead rule" in text
            return
    raise AssertionError("expected at least one reduce action")


def test_explain_accept_action():
    result = analyze(EXPRESSION, "SLR(1)")
    for (state, terminal), action in result.table.action.items():
        if action.action_type == "accept":
            text = explain_action(result, state, terminal)
            assert "ACCEPT" in text
            assert "augmented start" in text
            return
    raise AssertionError("expected an accept action")


def test_explain_error_cell():
    result = analyze(EXPRESSION, "SLR(1)")
    for state in range(result.table.num_states):
        for terminal in result.table.terminals:
            if result.table.get_action(state, terminal) is None:
                text = explain_action(result, state, terminal)
                assert "ERROR" in text
                return
    raise AssertionError("expected at least one empty ACTION cell")


def test_explain_goto():
    result = analyze(EXPRESSION, "SLR(1)")
    text = explain_goto(result, 0, "E")
    assert "GOTO[0, E]" in text
    assert "move dot over E" in text
    assert "Destination" in text