"""Tests for the central grammar engine: augmentation, symbol inspection,
and cyclic FIRST/FOLLOW safety."""

from __future__ import annotations

from core.first_follow import compute_first, compute_follow
from core.grammar_engine import augment_grammar, undefined_symbols, used_symbols
from core.grammar_parser import parse_grammar


def test_used_symbols():
    grammar = parse_grammar("S -> a A\nA -> b")
    assert used_symbols(grammar) == ["A", "a", "b"]


def test_undefined_symbols_heuristic():
    grammar = parse_grammar("S -> A B\nA -> a")
    # 'B' is an upper-case identifier used but never defined.
    assert undefined_symbols(grammar) == ["B"]


def test_undefined_symbols_ignore_terminals():
    grammar = parse_grammar("S -> id + id")
    assert undefined_symbols(grammar) == []


def test_augment_grammar_adds_new_start():
    grammar = parse_grammar("S -> a S | b")
    augmented = augment_grammar(grammar)
    assert augmented.start_symbol == "S'"
    assert augmented.has_production("S'", ["S"])
    # Original productions are preserved.
    assert augmented.has_production("S", ["a", "S"])
    # Terminals are unchanged.
    assert augmented.terminals == {"a", "b"}


def test_augment_grammar_avoids_collision():
    grammar = parse_grammar("S -> a\nS' -> b")
    augmented = augment_grammar(grammar)
    assert augmented.start_symbol != "S'"
    assert augmented.start_symbol.startswith("S'")


def test_first_terminates_on_cycle():
    grammar = parse_grammar("S -> A\nA -> B\nB -> A | b")
    first = compute_first(grammar)
    # B produces 'b', so it flows back through the cycle to A and S.
    assert "b" in first["A"]
    assert "b" in first["S"]


def test_first_handles_epsilon():
    grammar = parse_grammar("S -> A B\nA -> a | ε\nB -> b")
    first = compute_first(grammar)
    assert "ε" in first["A"]
    assert "b" in first["S"]
    assert "a" in first["S"]


def test_follow_start_has_end_marker():
    grammar = parse_grammar("S -> a S | b")
    first = compute_first(grammar)
    follow = compute_follow(grammar, first)
    assert "$" in follow["S"]


def test_follow_propagation_through_nullable():
    grammar = parse_grammar("S -> A B\nA -> a | ε\nB -> b")
    first = compute_first(grammar)
    follow = compute_follow(grammar, first)
    # B is at the end, so it inherits FOLLOW(S) = {$}.
    assert "$" in follow["B"]
    # A is followed by B, so FIRST(B) = {b} is in FOLLOW(A).
    assert "b" in follow["A"]