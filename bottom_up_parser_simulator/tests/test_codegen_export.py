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
# Code formatting
# ----------------------------------------------------------------------
def test_generated_code_is_valid_python(analysis):
    import ast

    code = generate_lr_parser(analysis)
    ast.parse(code)


def test_generated_code_docstring_has_metadata(analysis):
    code = generate_lr_parser(analysis)
    assert code.startswith('"""Auto-generated LR parser.')
    assert "Grammar summary" in code
    assert "SLR(1)" in code
    assert "States:" in code
    assert "Start symbol:" in code


def test_generated_code_has_all_and_main(analysis):
    code = generate_lr_parser(analysis)
    assert '__all__ = ["PRODUCTIONS", "ACTION", "GOTO", "tokenize", "LRParser", "main"]' in code
    assert "def main(tokens=None):" in code
    assert 'if __name__ == "__main__":' in code


def test_generated_code_has_section_banners(analysis):
    code = generate_lr_parser(analysis)
    assert "# PRODUCTIONS" in code
    assert "# ACTION TABLE" in code
    assert "# GOTO TABLE" in code
    assert "# TABLE-DRIVEN LR PARSER" in code
    assert "# DEMO" in code


def test_generated_main_parses_sample(analysis):
    code = generate_lr_parser(analysis, sample_input=["id", "+", "id", "*", "id"])
    namespace = {"__name__": "generated_module"}
    exec(compile(code, "<generated>", "exec"), namespace)
    assert namespace["main"](["id", "+", "id", "*", "id"]) is True
    assert namespace["main"](["id", "+"]) is False


def test_generated_module_runs_as_script(analysis, tmp_path):
    import subprocess
    import sys

    code = generate_lr_parser(analysis, sample_input=["id", "+", "id"])
    script = tmp_path / "generated_parser.py"
    script.write_text(code, encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert out.returncode == 0, out.stderr
    assert "ACCEPT" in out.stdout


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