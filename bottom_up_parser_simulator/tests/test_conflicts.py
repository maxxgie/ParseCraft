"""Tests for precedence parsing and conflict resolution."""

from __future__ import annotations

import pytest

from core.conflict_resolution import (
    FIRST,
    NONE,
    PRECEDENCE,
    REDUCE,
    SHIFT,
    ResolutionConfig,
)
from core.engine import analyze, simulate_input
from core.grammar_parser import parse_grammar
from core.precedence import LEFT, NONASSOC, RIGHT, parse_precedence

EXPR_PREC = """%left +
%left *
E -> E + E | E * E | ( E ) | id"""


def _middle_symbol(node):
    """Return the operator symbol of a binary parse-tree node."""
    return node.children[1].symbol


def _is_terminal_node(node):
    """Return True for an ``E -> id`` node (single terminal child)."""
    return len(node.children) == 1 and node.children[0].is_leaf()


# ----------------------------------------------------------------------
# Precedence parsing
# ----------------------------------------------------------------------
def test_parse_precedence_levels_and_assoc():
    info = parse_precedence(EXPR_PREC)
    assert info.level("+") == 1
    assert info.level("*") == 2
    assert info.assoc("+") == LEFT
    assert info.assoc("*") == LEFT
    assert len(info) == 2


def test_parse_precedence_right_and_nonassoc():
    info = parse_precedence("%right ^\n%nonassoc <")
    assert info.assoc("^") == RIGHT
    assert info.assoc("<") == NONASSOC


def test_parse_precedence_empty():
    info = parse_precedence("E -> E + E | id")
    assert len(info) == 0
    assert info.level("+") is None


def test_production_level_uses_rightmost_terminal():
    info = parse_precedence("%left +\n%left *")
    # E -> E + E has rightmost terminal '+', level 1
    assert info.production_level(["E", "+", "E"]) == 1
    assert info.production_level(["E", "*", "E"]) == 2


# ----------------------------------------------------------------------
# Conflict detection
# ----------------------------------------------------------------------
def test_expression_has_four_conflicts():
    result = analyze(EXPR_PREC, "SLR(1)")
    assert len(result.conflicts) == 4
    assert all(c.conflict_type == "shift-reduce" for c in result.conflicts)
    assert result.unresolved_conflicts == result.conflicts


def test_conflict_message_and_summary():
    result = analyze(EXPR_PREC, "SLR(1)")
    conflict = result.conflicts[0]
    assert "shift-reduce" in conflict.message
    assert conflict.actions_summary()


def test_precedence_declarations_skipped_by_grammar_parser():
    grammar = parse_grammar("%left +\nE -> E + E | id")
    assert grammar.terminals == {"+", "id"}
    assert grammar.has_production("E", ["E", "+", "E"])


# ----------------------------------------------------------------------
# Resolution strategies
# ----------------------------------------------------------------------
def test_resolution_config_validates():
    with pytest.raises(ValueError):
        analyze(EXPR_PREC, "SLR(1)", resolution=ResolutionConfig(enabled=True, shift_reduce="bogus"))


def test_prefer_shift_resolves_all():
    result = analyze(
        EXPR_PREC,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=SHIFT),
    )
    assert len(result.resolutions) == 4
    assert result.unresolved_conflicts == []
    for resolution in result.resolutions:
        assert resolution.chosen.action_type == "shift"


def test_prefer_reduce_resolves_all():
    result = analyze(
        EXPR_PREC,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=REDUCE),
    )
    assert result.unresolved_conflicts == []
    for resolution in result.resolutions:
        assert resolution.chosen.action_type == "reduce"


def test_precedence_makes_mul_bind_tighter():
    result = analyze(
        EXPR_PREC,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=PRECEDENCE),
    )
    assert result.unresolved_conflicts == []

    # State with E -> E + E . on '*': shift (because * binds tighter).
    mul_resolution = next(
        r
        for r in result.resolutions
        if r.terminal == "*" and r.chosen.action_type == "shift"
    )
    assert mul_resolution is not None

    # id + id * id -> root operator '+', right subtree operator '*'.
    sim = simulate_input(result, "id + id * id")
    assert sim.accepted
    root = sim.parse_tree
    assert _middle_symbol(root) == "+"
    assert _middle_symbol(root.children[2]) == "*"

    # id * id + id -> root operator '+', left subtree operator '*'.
    sim2 = simulate_input(result, "id * id + id")
    assert sim2.accepted
    assert _middle_symbol(sim2.parse_tree) == "+"
    assert _middle_symbol(sim2.parse_tree.children[0]) == "*"


def test_left_associativity():
    result = analyze(
        EXPR_PREC,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=PRECEDENCE),
    )
    sim = simulate_input(result, "id + id + id")
    assert sim.accepted
    root = sim.parse_tree
    # Left associative: (id + id) + id, so the left child is composite and
    # the right child is a terminal.
    assert _middle_symbol(root.children[0]) == "+"
    assert _is_terminal_node(root.children[2])


def test_right_associativity_shifts():
    result = analyze(
        "%right ^\nE -> E ^ E | id",
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=PRECEDENCE),
    )
    assert result.unresolved_conflicts == []
    sim = simulate_input(result, "id ^ id ^ id")
    assert sim.accepted
    root = sim.parse_tree
    # Right associative: id ^ (id ^ id), so the right child is composite and
    # the left child is a terminal.
    assert _is_terminal_node(root.children[0])
    assert _middle_symbol(root.children[2]) == "^"


def test_nonassoc_leaves_conflict_unresolved():
    result = analyze(
        "%nonassoc <\nE -> E < E | id",
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=PRECEDENCE),
    )
    assert len(result.conflicts) == 1
    assert result.resolutions == []
    assert len(result.unresolved_conflicts) == 1


def test_precedence_without_declarations_defaults_to_shift():
    # No %left lines: precedence strategy falls back to shift and still resolves.
    result = analyze(
        "E -> E + E | E * E | id",
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, shift_reduce=PRECEDENCE),
    )
    assert result.unresolved_conflicts == []


# ----------------------------------------------------------------------
# Reduce-reduce resolution
# ----------------------------------------------------------------------
def test_reduce_reduce_first_rule():
    grammar = """S -> A | B
A -> a
B -> a"""
    result = analyze(
        grammar,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=True, reduce_reduce=FIRST),
    )
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.conflict_type == "reduce-reduce"
    assert result.unresolved_conflicts == []
    resolution = result.resolutions[0]
    assert resolution.chosen.rule_number == min(
        a.rule_number for a in conflict.actions if a.action_type == "reduce"
    )
    # The chosen action must actually be written into the table.
    assert (
        result.table.get_action(conflict.state, conflict.terminal).to_string()
        == resolution.chosen.to_string()
    )


# ----------------------------------------------------------------------
# Engine integration
# ----------------------------------------------------------------------
def test_no_resolution_keeps_conflicts():
    result = analyze(EXPR_PREC, "SLR(1)")
    assert result.resolutions == []
    assert len(result.unresolved_conflicts) == len(result.conflicts)


def test_resolution_with_left_factoring_and_prefer_shift():
    grammar = """S -> if E then S | if E then S else S | other
E -> cond"""
    result = analyze(
        grammar,
        "SLR(1)",
        left_factoring=True,
        resolution=ResolutionConfig(enabled=True, shift_reduce=SHIFT),
    )
    assert result.unresolved_conflicts == []
    assert all(r.chosen.action_type == "shift" for r in result.resolutions)
    # The dangling-else is resolved in favour of shifting 'else'.
    assert simulate_input(result, "if cond then other else other").accepted


def test_disabled_resolution_reports_but_does_not_resolve():
    result = analyze(
        EXPR_PREC,
        "SLR(1)",
        resolution=ResolutionConfig(enabled=False, shift_reduce=SHIFT),
    )
    assert result.resolutions == []
    assert len(result.conflicts) == 4