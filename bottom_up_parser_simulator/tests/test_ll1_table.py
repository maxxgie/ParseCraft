"""Tests for LL(1) table generation, validation and cell explanations."""

from __future__ import annotations

from core.topdown.ll1 import (
    build_ll1_table,
    explain_ll1_cell,
    validate_ll1_table,
)

LL1_GRAMMAR = """E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id"""

FIRST_FIRST = """S -> A
A -> a | a b"""

FIRST_FOLLOW = """S -> A a
A -> a | ε"""


def _table_and_grammar(text):
    from core.grammar_parser import parse_grammar

    grammar = parse_grammar(text)
    return build_ll1_table(grammar), grammar


def test_ll1_table_is_conflict_free():
    table, grammar = _table_and_grammar(LL1_GRAMMAR)
    assert table.conflicts == []
    assert validate_ll1_table(table, grammar) == []


def test_ll1_table_entries():
    table, _ = _table_and_grammar(LL1_GRAMMAR)
    # M[E, id] = E -> T E'
    e_cell = table.cell("E", "id")
    assert len(e_cell) == 1
    nt, body = table.productions[e_cell[0]]
    assert nt == "E"
    assert body == ["T", "E'"]
    # M[E', +] = E' -> + T E'
    plus_cell = table.cell("E'", "+")
    assert table.productions[plus_cell[0]][1] == ["+", "T", "E'"]
    # M[E', $] = E' -> ε (placed via FOLLOW)
    dollar_cell = table.cell("E'", "$")
    assert table.productions[dollar_cell[0]][1] == []


def test_first_first_conflict_is_classified():
    table, grammar = _table_and_grammar(FIRST_FIRST)
    issues = validate_ll1_table(table, grammar)
    assert len(issues) == 1
    assert issues[0].kind == "FIRST/FIRST"
    assert "Left-factor" in issues[0].suggestion


def test_first_follow_conflict_is_classified():
    table, grammar = _table_and_grammar(FIRST_FOLLOW)
    issues = validate_ll1_table(table, grammar)
    assert len(issues) == 1
    assert issues[0].kind == "FIRST/FOLLOW"
    assert issues[0].suggestion


def test_explain_ll1_cell_single_production():
    table, grammar = _table_and_grammar(LL1_GRAMMAR)
    text = explain_ll1_cell(table, grammar, "E", "id")
    assert "M[E, id]" in text
    assert "Production r0" in text
    assert "FIRST" in text


def test_explain_ll1_cell_empty():
    table, grammar = _table_and_grammar(LL1_GRAMMAR)
    text = explain_ll1_cell(table, grammar, "E", "*")
    assert "Empty cell" in text


def test_explain_ll1_cell_conflict():
    table, grammar = _table_and_grammar(FIRST_FIRST)
    text = explain_ll1_cell(table, grammar, "A", "a")
    assert "Conflict" in text
    assert "Suggested fix" in text