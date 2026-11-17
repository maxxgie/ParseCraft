"""Tests for parser error reporting: expected tokens and solution hints."""

from __future__ import annotations

from core.engine import analyze, simulate_input
from core.topdown import analyze_topdown, simulate_topdown

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


def test_lr_error_lists_expected_tokens():
    result = analyze(GRAMMAR, "SLR(1)")
    sim = simulate_input(result, "id +")
    assert sim.accepted is False
    assert "Expected one of" in sim.error
    assert "state" in sim.error


def test_lr_error_mentions_solution_hint():
    result = analyze(GRAMMAR, "SLR(1)")
    sim = simulate_input(result, "id id")
    assert sim.accepted is False
    assert "Possible fix" in sim.error


def test_ll1_error_location_reported():
    grammar = (
        "E -> T E'\nE' -> + T E' | ε\nT -> F T'\n"
        "T' -> * F T' | ε\nF -> ( E ) | id"
    )
    result = analyze_topdown(grammar, "LL(1)")
    sim = simulate_topdown(result, "id +")
    assert sim.accepted is False
    assert sim.error is not None
    assert "LL(1) error" in sim.error or "Syntax error" in sim.error


def test_recursive_descent_reports_left_recursion():
    result = simulate_topdown(
        analyze_topdown(GRAMMAR, "Recursive Descent"), "id"
    )
    assert result.accepted is False
    assert "Left recursion" in (result.error or "")