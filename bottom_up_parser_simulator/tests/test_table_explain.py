"""Tests for the ACTION/GOTO table cell explanations."""

from __future__ import annotations

from core.engine import analyze
from core.table_explain import explain_action, explain_goto

GRAMMAR = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def _result(parser="SLR(1)"):
    return analyze(GRAMMAR, parser)


def test_explain_shift_cell():
    result = _result()
    table = result.table
    # Find any shift entry and explain it.
    shift = next(
        ((s, t, a) for (s, t), a in table.action.items() if a.action_type == "shift"),
        None,
    )
    assert shift is not None, "expected at least one shift entry"
    state, term, action = shift
    text = explain_action(result, state, term)
    assert f"ACTION[{state}, {term}]" in text
    assert f"SHIFT {action.state}" in text
    assert "immediately after the dot" in text


def test_explain_reduce_cell():
    result = _result()
    table = result.table
    reduce_entry = next(
        (
            (s, t, a)
            for (s, t), a in table.action.items()
            if a.action_type == "reduce"
        ),
        None,
    )
    assert reduce_entry is not None, "expected at least one reduce entry"
    state, term, action = reduce_entry
    text = explain_action(result, state, term)
    assert f"ACTION[{state}, {term}]" in text
    assert "REDUCE" in text
    assert f"r{action.rule_number}" in text


def test_explain_empty_cell_is_error():
    result = _result()
    table = result.table
    # Pick a state/terminal pair that has no action.
    terminals = sorted(result.grammar.terminals)
    found = None
    for state in range(table.num_states):
        for term in terminals:
            if table.get_action(state, term) is None:
                found = (state, term)
                break
        if found:
            break
    assert found is not None, "expected at least one empty ACTION cell"
    state, term = found
    text = explain_action(result, state, term)
    assert f"ACTION[{state}, {term}]" in text
    assert "ERROR" in text


def test_explain_goto_cell():
    result = _result()
    table = result.table
    goto_entry = next(
        ((s, nt, dst) for (s, nt), dst in table.goto.items()), None
    )
    assert goto_entry is not None, "expected at least one GOTO entry"
    state, nt, dst = goto_entry
    text = explain_goto(result, state, nt)
    assert f"GOTO[{state}, {nt}]" in text
    assert str(dst) in text