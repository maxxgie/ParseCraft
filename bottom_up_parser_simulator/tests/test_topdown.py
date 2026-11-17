"""Tests for top-down parsers: recursive descent, backtracking, LL(1)."""

from __future__ import annotations

import pytest

from core.grammar_parser import parse_grammar
from core.topdown import (
    TOPDOWN_METHODS,
    analyze_topdown,
    build_ll1_table,
    simulate_topdown,
)

# A left-factored, LL(1) expression grammar.
LL1_GRAMMAR = """E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id"""

# A left-recursive expression grammar (not usable by top-down parsers).
LEFT_REC = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


# ----------------------------------------------------------------------
# Analysis
# ----------------------------------------------------------------------
def test_analyze_reports_left_recursion():
    result = analyze_topdown(LEFT_REC, "Recursive Descent")
    assert result.left_recursion is True


def test_analyze_ll1_has_no_conflicts():
    result = analyze_topdown(LL1_GRAMMAR, "LL(1)")
    assert result.conflicts == []
    assert result.is_ll1 is True


def test_analyze_reports_ll1_conflicts():
    result = analyze_topdown(LEFT_REC, "Predictive (LL(1))")
    assert len(result.conflicts) > 0
    assert result.is_ll1 is False


def test_unknown_method_raises():
    from core.topdown import analyze_topdown as at

    with pytest.raises(ValueError):
        at(LL1_GRAMMAR, "Not A Parser")


# ----------------------------------------------------------------------
# LL(1) table
# ----------------------------------------------------------------------
def test_ll1_table_shape():
    table = build_ll1_table(parse_grammar(LL1_GRAMMAR))
    assert table.non_terminals == ["E", "E'", "T", "T'", "F"]
    assert "$" in table.terminals
    # E -> T E' is placed under FIRST(T) = {(, id}.
    assert table.cell("E", "id")
    # E' -> + T E' is placed under '+'.
    assert table.cell("E'", "+")
    # E' -> ε is placed under FOLLOW(E') which contains $.
    assert table.cell("E'", "$")


# ----------------------------------------------------------------------
# Acceptance / rejection across methods
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "method", ["Recursive Descent", "Predictive (LL(1))", "LL(1)"]
)
@pytest.mark.parametrize(
    "text", ["id", "id+id", "id+id*id", "(id+id)*id", "id*id+id"]
)
def test_accept_valid_inputs(method, text):
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, method), text)
    assert result.accepted, result.error


@pytest.mark.parametrize("method", ["Recursive Descent", "LL(1)"])
@pytest.mark.parametrize("text", ["id+", "+id", "()", "id id", "id**id"])
def test_reject_invalid_inputs(method, text):
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, method), text)
    assert result.accepted is False
    assert result.error is not None


def test_parse_tree_built_on_success():
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, "LL(1)"), "id")
    assert result.accepted
    root = result.parse_tree
    assert root is not None
    assert root.symbol == "E"


def test_steps_recorded():
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, "LL(1)"), "id+id")
    assert len(result.steps) > 0
    actions = {step.action for step in result.steps}
    assert "predict" in actions
    assert "match" in actions
    assert "accept" in actions


# ----------------------------------------------------------------------
# Recursive descent
# ----------------------------------------------------------------------
def test_recursive_descent_derivation():
    result = simulate_topdown(
        analyze_topdown(LL1_GRAMMAR, "Recursive Descent"), "id"
    )
    assert result.accepted
    assert any(lhs == "E" for lhs, _ in result.derivation)


def test_backtracking_records_failed_attempts():
    grammar = "S -> a S | a"
    result = simulate_topdown(
        analyze_topdown(grammar, "Backtracking Recursive Descent"), "a a"
    )
    assert result.accepted
    assert len(result.failed_attempts) > 0
    assert len(result.decision_points) > 0


# ----------------------------------------------------------------------
# Left recursion guard
# ----------------------------------------------------------------------
@pytest.mark.parametrize("method", TOPDOWN_METHODS)
def test_left_recursion_is_rejected(method):
    result = simulate_topdown(analyze_topdown(LEFT_REC, method), "id")
    assert result.accepted is False
    assert "Left recursion" in (result.error or "")


# ----------------------------------------------------------------------
# Transforms (left-recursion removal, left factoring) for top-down
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "method", ["Recursive Descent", "LL(1)", "Predictive (LL(1))"]
)
def test_left_recursion_removal_enables_parsing(method):
    result = analyze_topdown(
        LEFT_REC, method, remove_left_recursion=True, left_factoring=True
    )
    assert result.left_recursion is False
    result = simulate_topdown(result, "id+id*id")
    assert result.accepted, result.error


def test_topdown_transforms_recorded():
    result = analyze_topdown(LEFT_REC, "LL(1)", remove_left_recursion=True)
    assert "left-recursion removal" in result.transforms


def test_topdown_no_transform_when_not_needed():
    result = analyze_topdown(LL1_GRAMMAR, "LL(1)", remove_left_recursion=True)
    assert result.transforms == []


def test_left_factoring_transform():
    # Common prefixes are removed by left factoring.
    grammar = "S -> a b | a c"
    result = analyze_topdown(grammar, "LL(1)", left_factoring=True)
    assert "left factoring" in result.transforms
    assert result.left_factoring is False