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


def test_empty_grammar_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("   \n  ")


def test_duplicate_production_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("E -> a\nE -> a")


def test_epsilon_with_other_symbols_raises():
    with pytest.raises(GrammarParseError):
        parse_grammar("E -> ε a")


def test_comments_and_blank_lines_ignored():
    grammar = parse_grammar("# a comment\n\nE -> a\n")
    assert grammar.has_production("E", ["a"])