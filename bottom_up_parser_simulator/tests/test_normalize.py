"""Tests for grammar normalisation passes."""

from __future__ import annotations

import pytest

from core.engine import analyze, simulate_input
from core.grammar_normalize import (
    has_epsilon_productions,
    has_unit_productions,
    has_useless_symbols,
    normalize_grammar,
    remove_epsilon_productions,
    remove_unit_productions,
    remove_useless_symbols,
)
from core.grammar_parser import parse_grammar


# ----------------------------------------------------------------------
# Detection helpers
# ----------------------------------------------------------------------
def test_detect_epsilon():
    assert has_epsilon_productions(parse_grammar("S -> A\nA -> a | ε")) is True
    assert has_epsilon_productions(parse_grammar("S -> a")) is False


def test_detect_unit():
    assert has_unit_productions(parse_grammar("S -> A\nA -> a")) is True
    assert has_unit_productions(parse_grammar("S -> a A\nA -> b")) is False


def test_detect_useless():
    grammar = parse_grammar("S -> A a | b\nA -> A\nB -> b")
    assert has_useless_symbols(grammar) is True
    assert has_useless_symbols(parse_grammar("S -> a S | b")) is False


# ----------------------------------------------------------------------
# Epsilon removal
# ----------------------------------------------------------------------
def test_remove_epsilon_non_nullable_start():
    grammar = parse_grammar("S -> A B\nA -> a | ε\nB -> b")
    result = remove_epsilon_productions(grammar)
    assert has_epsilon_productions(result) is False
    # A -> a | ε combined with S -> A B gives S -> A B | B.
    assert result.has_production("S", ["A", "B"])
    assert result.has_production("S", ["B"])


def test_remove_epsilon_nullable_start_introduces_new_start():
    grammar = parse_grammar("S -> A B\nA -> a | ε\nB -> b | ε")
    result = remove_epsilon_productions(grammar)
    # A fresh start symbol is introduced and the only ε-production is its own.
    assert result.start_symbol != "S"
    epsilon_owners = [
        nt for nt, bodies in result.productions.items() if any(not b for b in bodies)
    ]
    assert epsilon_owners == [result.start_symbol]


@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_remove_epsilon_preserves_language(parser_type):
    grammar = "S -> A B\nA -> a | ε\nB -> b | ε"
    result = analyze(grammar, parser_type, remove_epsilon=True)
    for text in ["a b", "a", "b", ""]:
        assert simulate_input(result, text).accepted, text
    assert not simulate_input(result, "a a").accepted


def test_remove_epsilon_non_nullable_preserves_language():
    grammar = "S -> A B\nA -> a | ε\nB -> b"
    result = analyze(grammar, "SLR(1)", remove_epsilon=True)
    assert simulate_input(result, "a b").accepted
    assert simulate_input(result, "b").accepted
    assert not simulate_input(result, "a").accepted


# ----------------------------------------------------------------------
# Unit removal
# ----------------------------------------------------------------------
def test_remove_unit_basic():
    grammar = parse_grammar("S -> A | B\nA -> a\nB -> b")
    result = remove_unit_productions(grammar)
    assert has_unit_productions(result) is False
    assert result.has_production("S", ["a"])
    assert result.has_production("S", ["b"])


def test_remove_unit_chain():
    grammar = parse_grammar("S -> A\nA -> B\nB -> b")
    result = remove_unit_productions(grammar)
    assert has_unit_productions(result) is False
    assert result.has_production("S", ["b"])


def test_remove_unit_preserves_language():
    result = analyze("S -> A | B\nA -> a\nB -> b", "SLR(1)", remove_unit=True)
    assert simulate_input(result, "a").accepted
    assert simulate_input(result, "b").accepted
    assert not simulate_input(result, "a b").accepted


# ----------------------------------------------------------------------
# Useless-symbol removal
# ----------------------------------------------------------------------
def test_remove_useless_symbols():
    grammar = parse_grammar("S -> A a | b\nA -> A\nB -> b")
    result = remove_useless_symbols(grammar)
    assert "A" not in result.non_terminals  # non-generating
    assert "B" not in result.non_terminals  # unreachable
    assert result.has_production("S", ["b"])


def test_remove_useless_keeps_useful():
    grammar = parse_grammar("S -> A a | b\nA -> b")
    result = remove_useless_symbols(grammar)
    assert result.non_terminals == {"S", "A"}


# ----------------------------------------------------------------------
# Combined / engine integration
# ----------------------------------------------------------------------
def test_normalize_grammar_flags():
    # Non-nullable start: after ε-removal no empty bodies remain anywhere.
    grammar = parse_grammar("S -> A b | b\nA -> a | ε")
    result = normalize_grammar(grammar, remove_epsilon=True, remove_unit=True)
    assert has_epsilon_productions(result) is False
    assert has_unit_productions(result) is False


def test_analyze_records_only_applied_transforms():
    # Unit removal requested but the grammar has no unit productions.
    result = analyze("S -> a", "SLR(1)", remove_unit=True)
    assert result.transforms == []

    result2 = analyze("S -> A\nA -> a", "SLR(1)", remove_unit=True)
    assert "unit-production removal" in result2.transforms


def test_analyze_all_normalizations_together():
    result = analyze(
        "S -> A a | b\nA -> A | c | ε\nB -> b",
        "SLR(1)",
        remove_useless=True,
        remove_epsilon=True,
        remove_unit=True,
    )
    assert "useless-symbol removal" in result.transforms
    assert "ε-production removal" in result.transforms
    assert "unit-production removal" in result.transforms
    # The result must still be a usable grammar.
    assert len(result.automaton.states) > 0