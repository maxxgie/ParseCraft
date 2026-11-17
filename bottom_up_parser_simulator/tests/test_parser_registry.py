"""Tests for the parser table/non-table classification."""

from __future__ import annotations

from core.engine import ALL_PARSER_TYPES
from core.parser_registry import (
    PROCEDURE_PARSERS,
    TABLE_BASED_PARSERS,
    is_ll1_parser,
    is_lr_parser,
    is_procedure_parser,
    parse_table_kinds,
    procedure_trace_kind,
    uses_parse_table,
)
from core.topdown import TOPDOWN_METHODS

ALL_PARSERS = ALL_PARSER_TYPES + TOPDOWN_METHODS


def test_every_parser_is_classified():
    for parser in ALL_PARSERS:
        assert uses_parse_table(parser) or is_procedure_parser(parser), parser


def test_classification_is_exhaustive_and_disjoint():
    classified = set(TABLE_BASED_PARSERS) | set(PROCEDURE_PARSERS)
    assert classified == set(ALL_PARSERS)
    assert not (set(TABLE_BASED_PARSERS) & set(PROCEDURE_PARSERS))


def test_ll1_parsers_use_the_ll_table():
    for parser in ["Predictive (LL(1))", "LL(1)"]:
        assert is_ll1_parser(parser)
        assert not is_lr_parser(parser)
        assert uses_parse_table(parser)
        assert parse_table_kinds(parser) == ["LL(1)"]


def test_lr_parsers_use_action_and_goto():
    for parser in ["Shift Reduce", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]:
        assert is_lr_parser(parser)
        assert uses_parse_table(parser)
        assert parse_table_kinds(parser) == ["ACTION", "GOTO"]


def test_procedure_parsers_have_no_table():
    for parser in ["Recursive Descent", "Backtracking Recursive Descent"]:
        assert is_procedure_parser(parser)
        assert not uses_parse_table(parser)
        assert parse_table_kinds(parser) == []
        assert procedure_trace_kind(parser)