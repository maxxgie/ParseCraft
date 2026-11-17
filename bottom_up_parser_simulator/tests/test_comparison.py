"""Tests for the parser comparison module."""

from __future__ import annotations

from core.comparison import PARSER_ORDER, compare_parsers

LL1_GRAMMAR = """E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id"""

LEFT_REC_GRAMMAR = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def test_all_parsers_represented():
    report = compare_parsers(LL1_GRAMMAR)
    names = [s.parser for s in report.parser_stats]
    assert names == PARSER_ORDER


def test_ll1_grammar_is_ll1_compatible():
    report = compare_parsers(LL1_GRAMMAR)
    ll1 = next(s for s in report.parser_stats if s.parser == "LL(1)")
    assert ll1.compatible is True
    assert ll1.conflict_free is True
    assert ll1.conflicts == 0
    assert ll1.num_states is None


def test_ll1_grammar_has_lr_states():
    report = compare_parsers(LL1_GRAMMAR)
    lr0 = next(s for s in report.parser_stats if s.parser == "LR(0)")
    slr = next(s for s in report.parser_stats if s.parser == "SLR(1)")
    clr = next(s for s in report.parser_stats if s.parser == "CLR(1)")
    lalr = next(s for s in report.parser_stats if s.parser == "LALR(1)")
    assert lr0.num_states > 0
    # CLR(1) has at least as many states as LALR(1).
    assert clr.num_states >= lalr.num_states
    assert slr.conflicts == 0


def test_left_recursive_grammar_not_ll1():
    report = compare_parsers(LEFT_REC_GRAMMAR)
    ll1 = next(s for s in report.parser_stats if s.parser == "LL(1)")
    assert ll1.compatible is False
    assert "left recursion" in ll1.reason.lower()


def test_lr0_conflicts_reported():
    report = compare_parsers(LEFT_REC_GRAMMAR)
    lr0 = next(s for s in report.parser_stats if s.parser == "LR(0)")
    assert lr0.conflicts > 0
    assert lr0.conflict_free is False


def test_summary_mentions_parsers():
    report = compare_parsers(LL1_GRAMMAR)
    summary = report.summary()
    assert "LL(1)" in summary
    assert "LALR(1)" in summary


def test_as_row_shape():
    report = compare_parsers(LL1_GRAMMAR)
    row = report.parser_stats[0].as_row()
    assert len(row) == 3
    assert row[0] == "LL(1)"


def test_report_has_grammar_text_and_suggestion():
    report = compare_parsers(LL1_GRAMMAR)
    assert "E ->" in report.grammar_text
    assert report.suggested is not None
    assert report.suggested in [s.parser for s in report.parser_stats]