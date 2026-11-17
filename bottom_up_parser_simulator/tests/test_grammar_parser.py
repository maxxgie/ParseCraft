"""Tests for the BNF grammar parser."""

from __future__ import annotations

import pytest

from core.grammar_parser import GrammarParseError, parse_grammar
from models.grammar import Grammar

EXPRESSION = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def test_parse_basic():
    grammar = parse_grammar(EXPRESSION)
    assert grammar.start_symbol == "E"
    assert set(grammar.non_terminals) == {"E", "T", "F"}
    assert grammar.terminals == {"+", "*", "(", ")", "id"}
    assert grammar.has_production("E", ["E", "+", "T"])
    assert grammar.has_production("E", ["T"])


def test_round_trip_to_text():
    grammar = parse_grammar(EXPRESSION)
    reparsed = parse_grammar(grammar.to_text())
    assert reparsed.productions == grammar.productions


def test_explicit_epsilon_is_empty_production():
    grammar = parse_grammar("S -> A\nA -> a | ε")
    assert grammar.has_production("A", [])
    assert grammar.has_production("A", ["a"])
    assert "ε" not in grammar.terminals


def test_implicit_epsilon_empty_alternative():
    grammar = parse_grammar("S -> A\nA -> a |")
    assert grammar.has_production("A", [])


def test_missing_arrow_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("E T")


def test_invalid_operator_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("E = E T")


def test_invalid_operator_message():
    with pytest.raises(GrammarParseError) as exc:
        parse_grammar("E -> a\nE = E T")
    assert "Invalid production operator" in str(exc.value)


def test_missing_left_side_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("-> a b")


def test_missing_left_side_message():
    with pytest.raises(GrammarParseError) as exc:
        parse_grammar("-> a b")
    assert "no left-hand non-terminal" in str(exc.value)


def test_missing_right_side_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("A ->")


def test_missing_right_side_message():
    with pytest.raises(GrammarParseError) as exc:
        parse_grammar("A ->")
    assert "no derivation" in str(exc.value)


def test_empty_grammar_message():
    with pytest.raises(GrammarParseError) as exc:
        parse_grammar("   ")
    assert "cannot be empty" in str(exc.value)


def test_empty_grammar_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("   \n  ")


def test_duplicate_production_is_deduped():
    grammar = parse_grammar("E -> a\nE -> a")
    # The duplicate is removed from the productions but recorded for reporting.
    assert grammar.productions["E"] == [["a"]]
    assert grammar.duplicates == ["E -> a"]


def test_epsilon_with_other_symbols_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("E -> ε a")


def test_comments_and_blank_lines_ignored():
    grammar = parse_grammar("# a comment\n\nE -> a\n")
    assert grammar.has_production("E", ["a"])