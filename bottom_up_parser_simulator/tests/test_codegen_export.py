"""Tests for parser code generation and export."""

from __future__ import annotations

import pytest

from core.codegen import generate_lr_parser
from core.engine import analyze
from core.exporter import (
    analysis_to_html,
    analysis_to_markdown,
    automaton_to_dot,
    table_to_csv,
)

EXPR = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


@pytest.fixture(scope="module")
def analysis():
    return analyze(EXPR, "SLR(1)")


# ----------------------------------------------------------------------
# Code generation
# ----------------------------------------------------------------------
def test_generate_contains_class_and_tables(analysis):
    code = generate_lr_parser(analysis)
    assert "class LRParser" in code
    assert "PRODUCTIONS" in code
    assert "ACTION" in code
    assert "GOTO" in code
    assert "def parse(self, tokens)" in code


def test_generated_parser_runs(analysis):
    code = generate_lr_parser(analysis)
    namespace = {"__name__": "generated_module"}
    exec(compile(code, "<generated>", "exec"), namespace)

    parser_cls = namespace["LRParser"]
    assert parser_cls().parse(["id", "+", "id", "*", "id"]) is True
    assert parser_cls().parse(["id", "+"]) is False
    assert parser_cls().parse(["(", "id", ")", "*", "id"]) is True
    assert parser_cls().parse(["id", "id"]) is False


def test_generated_parser_trace(analysis):
    code = generate_lr_parser(analysis)
    namespace = {"__name__": "generated_module"}
    exec(compile(code, "<generated>", "exec"), namespace)
    parser = namespace["LRParser"]()
    assert parser.parse(["id"]) is True
    assert any(step[0] == "accept" for step in parser.trace)


def test_generated_parser_uses_sample_input(analysis):
    code = generate_lr_parser(analysis, sample_input=["id", "+", "id"])
    assert "['id', '+', 'id']" in code


def test_generated_parser_custom_class_name(analysis):
    code = generate_lr_parser(analysis, class_name="MyParser")
    assert "class MyParser" in code
    namespace = {"__name__": "generated_module"}
    exec(compile(code, "<generated>", "exec"), namespace)
    assert namespace["MyParser"]().parse(["id"]) is True


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------
def test_csv_has_header_and_rows(analysis):
    csv = table_to_csv(analysis)
    lines = csv.splitlines()
    assert lines[0] == "Table,State,Symbol,Entry"
    assert any(line.startswith("ACTION,") for line in lines)
    assert any(line.startswith("GOTO,") for line in lines)


def test_markdown_has_sections(analysis):
    md = analysis_to_markdown(analysis)
    assert "# Analysis Report" in md
    assert "## Grammar" in md
    assert "## FIRST / FOLLOW" in md
    assert "## ACTION Table" in md
    assert "## GOTO Table" in md


def test_html_has_tables(analysis):
    html = analysis_to_html(analysis)
    assert "<!DOCTYPE html>" in html
    assert html.count("<table>") == 2
    assert "ACTION Table" in html


def test_dot_starts_with_digraph(analysis):
    dot = automaton_to_dot(analysis)
    assert dot.startswith("digraph")
    assert "->" in dot


def test_export_with_conflicts():
    result = analyze("S -> A | B\nA -> a\nB -> a", "SLR(1)")
    md = analysis_to_markdown(result)
    assert "## Conflicts" in md
    assert "reduce-reduce" in md