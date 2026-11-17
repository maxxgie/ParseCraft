"""Tests for the grammar analyzer."""

from __future__ import annotations

import pytest

from core.grammar_analyzer import analyze_grammar
from core.grammar_parser import parse_grammar


def _codes(report, level=None):
    return [
        i.code for i in report.issues if level is None or i.level == level
    ]


def test_clean_grammar_has_no_errors():
    report = analyze_grammar(parse_grammar("S -> a S | b"))
    assert report.is_ok
    assert report.errors == []


def test_left_recursion_reported():
    report = analyze_grammar(parse_grammar("E -> E + id | id"))
    assert "left_recursion" in _codes(report)
    assert not report.is_ok is False  # left recursion is a warning, not error


def test_unreachable_reported():
    report = analyze_grammar(parse_grammar("S -> a\nA -> b"))
    assert "unreachable" in _codes(report)


def test_non_productive_reported():
    report = analyze_grammar(parse_grammar("S -> A\nA -> A"))
    assert "non_productive" in _codes(report)


def test_unit_cycle_reported():
    report = analyze_grammar(parse_grammar("S -> A\nA -> B\nB -> A | b"))
    assert "unit_cycle" in _codes(report)


def test_undefined_symbol_reported():
    report = analyze_grammar(parse_grammar("S -> a Y"), {"a"})
    assert "undefined_nonterminal" in _codes(report, "error")
    assert not report.is_ok


def test_undefined_nonterminal_by_heuristic():
    # Upper-case identifier used but never defined, no terminal declaration.
    report = analyze_grammar(parse_grammar("S -> A B\nA -> a"))
    assert "undefined_nonterminal" in _codes(report, "error")


def test_left_factoring_suggested():
    report = analyze_grammar(parse_grammar("S -> a b | a c"))
    assert "left_factoring" in _codes(report)


def test_ll1_conflicts_reported():
    report = analyze_grammar(parse_grammar("S -> S a | b"))
    assert "ll1_conflict" in _codes(report)


def test_ll1_grammar_is_clean():
    report = analyze_grammar(
        parse_grammar(
            "E -> T E'\nE' -> + T E' | ε\nT -> id"
        )
    )
    assert "ll1_conflict" not in _codes(report)


def test_duplicate_production_is_warning():
    from models.grammar import Grammar

    grammar = Grammar(
        start_symbol="S",
        productions={"S": [["a"], ["a"]]},
    )
    report = analyze_grammar(grammar)
    assert "duplicate_production" in _codes(report, "warning")


def test_summary_counts():
    report = analyze_grammar(parse_grammar("S -> S a | b"))
    assert "error" in report.summary()