"""Validation of a generated ACTION/GOTO parsing table.

Checks the textbook invariants that must hold for any LR parsing table:

* all states exist (contiguous ``0..n-1``);
* every DFA transition points to a valid state;
* every reduction references a real production;
* ``ACCEPT`` appears only for the augmented start rule, only on ``$``;
* ACTION columns are terminals only;
* GOTO columns are non-terminals only;
* conflicts are reported (not hidden);
* each parser type respects its own reduction rule.
"""

from __future__ import annotations

from typing import List

from core.automaton import ValidationIssue
from core.table_builder import assign_production_numbers

END_MARKER = "$"


def validate_parsing_table(analysis, conflicts=None) -> List[ValidationIssue]:
    """Validate a generated parsing table.

    Args:
        analysis: The :class:`~core.engine.AnalysisResult` to validate.
        conflicts: Optional conflict list; defaults to ``analysis.conflicts``.

    Returns:
        A list of :class:`~core.automaton.ValidationIssue`; empty ``ok`` flags
        indicate a textbook-correct table.
    """
    table = analysis.table
    grammar = analysis.grammar
    automaton = analysis.automaton
    issues: List[ValidationIssue] = []

    state_ids = {s.state_id for s in automaton.states}
    expected = set(range(table.num_states))

    # 1. All states exist.
    if state_ids == expected and table.num_states == len(automaton.states):
        issues.append(ValidationIssue(None, "All states exist", True))
    else:
        issues.append(
            ValidationIssue(
                None,
                "All states exist",
                False,
                "state ids are not contiguous 0..n-1",
            )
        )

    # 2. Transitions point to valid states.
    bad_transitions = [
        (src, sym, dst)
        for (src, sym), dst in automaton.transitions.items()
        if dst not in state_ids
    ]
    if bad_transitions:
        issues.append(
            ValidationIssue(
                None,
                "Transitions valid",
                False,
                f"{len(bad_transitions)} transition(s) target a missing state",
            )
        )
    else:
        issues.append(ValidationIssue(None, "Transitions valid", True))

    # 3. Reductions reference a valid production.
    numbers, _rules = assign_production_numbers(grammar)
    valid_rules = set(numbers.values())
    bad_reduces = [
        (state, term, action.rule_number)
        for (state, term), action in table.action.items()
        if action.action_type == "reduce" and action.rule_number not in valid_rules
    ]
    if bad_reduces:
        issues.append(
            ValidationIssue(
                None,
                "Reductions valid",
                False,
                f"{len(bad_reduces)} reduction(s) use an unknown production",
            )
        )
    else:
        issues.append(ValidationIssue(None, "Reductions valid", True))

    # 4. ACCEPT only for the augmented start rule, only on the end marker.
    aug = getattr(automaton, "augmented_grammar", None)
    aug_start = aug.start_symbol if aug is not None else "S'"
    accepts = [
        (state, term)
        for (state, term), action in table.action.items()
        if action.action_type == "accept"
    ]
    bad_accept: List[str] = []
    for state, term in accepts:
        if term != END_MARKER:
            bad_accept.append(f"I{state}: accept not on '$'")
            continue
        state_obj = automaton.get_state(state)
        has_aug = any(
            it.is_complete() and it.lhs == aug_start for it in state_obj.items
        )
        if not has_aug:
            bad_accept.append(f"I{state}: accept without augmented start item")
    if bad_accept:
        issues.append(
            ValidationIssue(
                None, "Accept rule", False, "; ".join(bad_accept)
            )
        )
    else:
        issues.append(
            ValidationIssue(
                None,
                "Accept rule",
                True,
                f"{len(accepts)} accept entry(ies)" if accepts else "no accept entry",
            )
        )

    # 5. ACTION columns are terminals only.
    bad_action = [
        (state, term)
        for (state, term) in table.action
        if term != END_MARKER and term not in grammar.terminals
    ]
    if bad_action:
        issues.append(
            ValidationIssue(
                None,
                "ACTION terminals only",
                False,
                f"{len(bad_action)} ACTION column(s) are not terminals",
            )
        )
    else:
        issues.append(ValidationIssue(None, "ACTION terminals only", True))

    # 6. GOTO columns are non-terminals only.
    bad_goto = [
        (state, nt) for (state, nt) in table.goto if nt not in grammar.non_terminals
    ]
    if bad_goto:
        issues.append(
            ValidationIssue(
                None,
                "GOTO non-terminals only",
                False,
                f"{len(bad_goto)} GOTO column(s) are not non-terminals",
            )
        )
    else:
        issues.append(ValidationIssue(None, "GOTO non-terminals only", True))

    # 7. Conflicts are reported (never hidden).
    if conflicts is None:
        conflicts = analysis.conflicts
    if conflicts:
        issues.append(
            ValidationIssue(
                None,
                "Conflicts reported",
                False,
                f"{len(conflicts)} conflict(s) present",
            )
        )
    else:
        issues.append(ValidationIssue(None, "No conflicts", True))

    # 8. Parser-type reduction rule respected.
    bad_rule: List[str] = []
    for (state, term), action in table.action.items():
        if action.action_type != "reduce":
            continue
        lhs = action.production_lhs
        body = action.production_rhs or ()
        mode = analysis.mode
        if mode == "lr0":
            ok = True
        elif mode == "slr1":
            ok = term in analysis.follow.get(lhs, set())
        else:  # clr1 / lalr1: the lookahead must belong to a completed item
            state_obj = automaton.get_state(state)
            ok = any(
                it.is_complete()
                and it.lhs == lhs
                and it.rhs == body
                and it.lookahead == term
                for it in state_obj.items
            )
        if not ok:
            bad_rule.append(f"I{state}:{term}->{lhs}")
    if bad_rule:
        issues.append(
            ValidationIssue(
                None,
                "Parser-type rule",
                False,
                f"{len(bad_rule)} reduction(s) violate the {analysis.parser_type} rule",
            )
        )
    else:
        issues.append(ValidationIssue(None, "Parser-type rule", True))

    return issues