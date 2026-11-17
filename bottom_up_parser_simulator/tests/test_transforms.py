"""Tests for left-recursion removal and left factoring."""

from __future__ import annotations

import pytest

from core.engine import analyze, grammar_features, simulate_input
from core.grammar_parser import parse_grammar
from core.grammar_transform import (
    apply_transforms,
    describe_features,
    eliminate_left_recursion,
    has_common_prefixes,
    has_left_recursion,
    left_factor,
)

EXPRESSION = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""

PREFIX_GRAMMAR = """S -> a b c | a b d | a e"""


# ----------------------------------------------------------------------
# Availability checks
# ----------------------------------------------------------------------
def test_detects_left_recursion():
    grammar = parse_grammar(EXPRESSION)
    assert has_left_recursion(grammar) is True


def test_no_left_recursion_in_right_recursive_grammar():
    grammar = parse_grammar("S -> a S | b")
    assert has_left_recursion(grammar) is False


def test_detects_common_prefixes():
    grammar = parse_grammar(PREFIX_GRAMMAR)
    assert has_common_prefixes(grammar) is True


def test_no_common_prefixes_in_expression():
    grammar = parse_grammar(EXPRESSION)
    assert has_common_prefixes(grammar) is False


def test_grammar_features_helper():
    features = grammar_features(EXPRESSION)
    assert features["left_recursion"] is True
    assert features["note"] == "left recursion detected"


# ----------------------------------------------------------------------
# Left-recursion removal
# ----------------------------------------------------------------------
def test_eliminate_immediate_left_recursion():
    grammar = parse_grammar("E -> E + T | T\nT -> id")
    result = eliminate_left_recursion(grammar)
    assert has_left_recursion(result) is False
    assert result.has_production("E", ["T", "E'"])
    assert result.has_production("E'", ["+", "T", "E'"])
    assert result.has_production("E'", [])


def test_eliminate_left_recursion_expression():
    grammar = parse_grammar(EXPRESSION)
    result = eliminate_left_recursion(grammar)
    assert has_left_recursion(result) is False
    assert result.start_symbol == "E"
    # The transformed grammar is SLR(1) and parses the same language.
    analysis = analyze(EXPRESSION, "SLR(1)", remove_left_recursion=True)
    assert analysis.conflicts == []
    assert simulate_input(analysis, "id + id * id").accepted


def test_eliminate_indirect_left_recursion():
    grammar = parse_grammar("S -> A a | b\nA -> S b | c")
    assert has_left_recursion(grammar) is True
    result = eliminate_left_recursion(grammar)
    assert has_left_recursion(result) is False


def test_eliminate_left_recursion_preserves_no_recursion_grammar():
    grammar = parse_grammar("S -> a S | b")
    result = eliminate_left_recursion(grammar)
    assert result.productions == grammar.productions


def test_eliminate_left_recursion_avoids_augmented_name():
    # Start symbol 'S' must not produce a bare "S'" (collides with augmentation).
    grammar = parse_grammar("S -> S a | b")
    result = eliminate_left_recursion(grammar)
    assert "S'" not in result.non_terminals
    # And the result still works with the LR automaton.
    analysis = analyze("S -> S a | b", "SLR(1)", remove_left_recursion=True)
    assert analysis.conflicts == []
    assert simulate_input(analysis, "b a a").accepted


def test_eliminate_left_recursion_with_epsilon():
    grammar = parse_grammar("S -> A\nA -> A a | ε")
    result = eliminate_left_recursion(grammar)
    assert has_left_recursion(result) is False
    analysis = analyze("S -> A\nA -> A a | ε", "SLR(1)", remove_left_recursion=True)
    assert simulate_input(analysis, "a a").accepted
    assert simulate_input(analysis, "").accepted


# ----------------------------------------------------------------------
# Left factoring
# ----------------------------------------------------------------------
def test_left_factor_common_prefixes():
    grammar = parse_grammar(PREFIX_GRAMMAR)
    result = left_factor(grammar)
    assert has_common_prefixes(result) is False
    # S must begin with 'a' followed by a single new non-terminal.
    assert any(
        len(body) == 2 and body[0] == "a" and body[1] in result.non_terminals
        for body in result.productions["S"]
    )
    # Language preserved.
    analysis = analyze(PREFIX_GRAMMAR, "CLR(1)", left_factoring=True)
    assert analysis.conflicts == []
    for text in ["a b c", "a b d", "a e"]:
        assert simulate_input(analysis, text).accepted, text
    assert not simulate_input(analysis, "a b").accepted


def test_left_factor_prefix_problem():
    # 'a' is a prefix of 'a b' -> factored with an epsilon alternative.
    grammar = parse_grammar("S -> a | a b")
    result = left_factor(grammar)
    assert has_common_prefixes(result) is False
    s_prods = result.productions["S"]
    sub = next(
        body[1] for body in s_prods if len(body) == 2 and body[0] == "a"
    )
    assert [] in result.productions[sub]
    assert ["b"] in result.productions[sub]
    # Language preserved.
    analysis = analyze("S -> a | a b", "CLR(1)", left_factoring=True)
    assert simulate_input(analysis, "a").accepted
    assert simulate_input(analysis, "a b").accepted


def test_left_factor_preserves_language():
    analysis = analyze(PREFIX_GRAMMAR, "CLR(1)", left_factoring=True)
    assert analysis.conflicts == []
    for text in ["a b c", "a b d", "a e"]:
        assert simulate_input(analysis, text).accepted, text
    assert not simulate_input(analysis, "a b").accepted


def test_left_factor_dangling_else():
    grammar = """S -> if E then S | if E then S else S | other
E -> cond"""
    result = left_factor(parse_grammar(grammar))
    assert has_common_prefixes(result) is False


# ----------------------------------------------------------------------
# Combined / engine integration
# ----------------------------------------------------------------------
def test_apply_transforms_order():
    grammar = parse_grammar(EXPRESSION)
    result = apply_transforms(grammar, remove_left_recursion=True, left_factoring=True)
    assert has_left_recursion(result) is False
    assert has_common_prefixes(result) is False


def test_analyze_records_transforms():
    analysis = analyze(EXPRESSION, "SLR(1)", remove_left_recursion=True)
    assert analysis.transforms == ["left-recursion removal"]
    assert "E'" in analysis.grammar.non_terminals


def test_analyze_without_transforms_keeps_original():
    analysis = analyze(EXPRESSION, "SLR(1)")
    assert analysis.transforms == []
    assert analysis.grammar.productions == parse_grammar(EXPRESSION).productions


def test_describe_features():
    assert describe_features(parse_grammar(EXPRESSION)) == "left recursion detected"
    assert (
        describe_features(parse_grammar(PREFIX_GRAMMAR))
        == "common prefixes detected"
    )
    assert (
        describe_features(parse_grammar("S -> a S | b"))
        == "no left recursion or common prefixes"
    )


# ----------------------------------------------------------------------
# Textbook ordering of transformed non-terminals
# ----------------------------------------------------------------------
def test_left_recursion_helper_immediately_follows_parent():
    result = eliminate_left_recursion(parse_grammar(EXPRESSION))
    assert list(result.productions.keys()) == ["E", "E'", "T", "T'", "F"]


def test_left_factor_helper_immediately_follows_parent():
    result = left_factor(parse_grammar(PREFIX_GRAMMAR))
    keys = list(result.productions.keys())
    assert keys[0] == "S"
    # The first helper is inserted directly after its parent, not at the end.
    assert keys[1].startswith("S'")


def test_left_factor_nested_helpers_follow_their_parent():
    result = left_factor(parse_grammar("S -> a b c | a b d | a e"))
    keys = list(result.productions.keys())
    assert keys[0] == "S"
    assert keys[1].startswith("S'")
    assert keys[2].startswith("S'")