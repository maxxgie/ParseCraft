"""Tests for parsing-table validation."""

from __future__ import annotations

from core.engine import analyze
from core.table_validation import validate_parsing_table

EXPRESSION = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def test_validation_all_ok_for_slr():
    result = analyze(EXPRESSION, "SLR(1)")
    issues = validate_parsing_table(result)
    failures = [issue for issue in issues if not issue.ok]
    assert failures == []


def test_validation_reports_lr0_conflicts():
    result = analyze(EXPRESSION, "LR(0)")
    issues = validate_parsing_table(result)
    by_check = {issue.check: issue for issue in issues}
    assert by_check["Conflicts reported"].ok is False


def test_validation_checks_present():
    result = analyze(EXPRESSION, "SLR(1)")
    checks = {issue.check for issue in validate_parsing_table(result)}
    for expected in [
        "All states exist",
        "Transitions valid",
        "Reductions valid",
        "Accept rule",
        "ACTION terminals only",
        "GOTO non-terminals only",
        "Parser-type rule",
    ]:
        assert expected in checks


def test_validation_ok_for_all_parser_types():
    for parser_type in ["LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]:
        result = analyze(EXPRESSION, parser_type)
        issues = validate_parsing_table(result)
        # Structural checks must pass for every parser type; only conflict
        # reporting is expected to fail for grammars that are not LR(0).
        by_check = {issue.check: issue for issue in issues}
        for check in [
            "All states exist",
            "Transitions valid",
            "Reductions valid",
            "Accept rule",
            "ACTION terminals only",
            "GOTO non-terminals only",
            "Parser-type rule",
        ]:
            assert by_check[check].ok is True, f"{parser_type}: {check} failed"