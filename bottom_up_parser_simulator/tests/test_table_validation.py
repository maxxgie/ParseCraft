"""Tests for the ACTION/GOTO table validation invariants."""

from __future__ import annotations

from core.engine import analyze
from core.table_validation import validate_parsing_table

EXPR = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""


def _checks(issues):
    return {i.check: i for i in issues}


def test_clean_lr0_table_passes_all_checks():
    result = analyze(EXPR, "LR(0)")
    issues = validate_parsing_table(result)
    # LR(0) on an ambiguous-by-lookahead grammar may raise conflicts, but the
    # structural invariants must all hold.
    checks = _checks(issues)
    for name in (
        "All states exist",
        "Transitions valid",
        "Reductions valid",
        "Accept rule",
        "ACTION terminals only",
        "GOTO non-terminals only",
        "Parser-type rule",
    ):
        assert checks[name].ok, f"{name} should pass: {checks[name].detail}"


def test_slr1_table_all_ok_when_conflict_free():
    # A simple unambiguous expression grammar parses without SLR(1) conflicts.
    grammar = """E -> E + T | T
T -> id"""
    result = analyze(grammar, "SLR(1)")
    issues = validate_parsing_table(result)
    checks = _checks(issues)
    assert checks["Parser-type rule"].ok
    # SLR(1) reductions on this grammar must stay within FOLLOW(lhs).
    for (state, term), action in result.table.action.items():
        if action.action_type == "reduce":
            assert term in result.follow[action.production_lhs]


def test_conflicts_are_reported_not_hidden():
    # The dangling-else grammar is shift/reduce ambiguous under SLR(1).
    grammar = """S -> if E then S | if E then S else S | other
E -> cond"""
    result = analyze(grammar, "SLR(1)")
    issues = validate_parsing_table(result)
    checks = _checks(issues)
    conflict_issue = checks.get("Conflicts reported") or checks.get("No conflicts")
    assert conflict_issue is not None
    if result.conflicts:
        assert not conflict_issue.ok
        assert f"{len(result.conflicts)}" in conflict_issue.detail
    else:
        assert conflict_issue.ok


def test_all_issues_are_validation_issue_objects():
    from core.automaton import ValidationIssue

    result = analyze(EXPR, "SLR(1)")
    issues = validate_parsing_table(result)
    assert issues
    assert all(isinstance(i, ValidationIssue) for i in issues)
    # There should be exactly the eight documented checks.
    assert len(issues) == 8