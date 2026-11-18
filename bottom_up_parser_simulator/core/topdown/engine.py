"""High-level entry points for top-down parsing."""

from __future__ import annotations

from typing import List

from core.first_follow import compute_first, compute_follow
from core.grammar_normalize import (
    remove_epsilon_productions,
    remove_unit_productions,
    remove_useless_symbols,
)
from core.grammar_parser import parse_grammar
from core.grammar_transform import (
    apply_transforms,
    build_grammar_stages,
    has_common_prefixes,
    has_left_recursion,
)
from core.logging_config import get_logger
from core.parser_simulator import tokenize
from core.topdown.backtracking import BacktrackingRecursiveDescentParser
from core.topdown.common import (
    END_MARKER,
    TOPDOWN_METHODS,
    TopDownResult,
    TopDownStep,
)
from core.topdown.ll1 import build_ll1_table, parse_predictive
from core.topdown.recursive_descent import RecursiveDescentParser

logger = get_logger(__name__)

LEFT_RECURSION_ERROR = (
    "Left recursion detected. Top-down parsers cannot handle left-recursive "
    "grammars; apply left-recursion removal first (Grammar options)."
)


def analyze_topdown(
    text: str,
    method: str,
    remove_left_recursion: bool = False,
    left_factoring: bool = False,
    remove_epsilon: bool = False,
    remove_unit: bool = False,
    remove_useless: bool = False,
) -> TopDownResult:
    """Parse ``text`` and prepare a top-down analysis for ``method``.

    Args:
        text: Grammar text in BNF format.
        method: One of :data:`~core.topdown.common.TOPDOWN_METHODS`.
        remove_left_recursion: Apply left-recursion removal before analysis.
        left_factoring: Apply left factoring before analysis.
        remove_epsilon: Eliminate ε-productions before analysis.
        remove_unit: Eliminate unit productions before analysis.
        remove_useless: Eliminate unreachable/non-generating symbols.

    Returns:
        A :class:`~core.topdown.common.TopDownResult` (without a parse yet).

    Raises:
        ValueError: If ``method`` is unknown.
    """
    if method not in TOPDOWN_METHODS:
        raise ValueError(
            f"Unknown top-down method '{method}'. Expected one of {TOPDOWN_METHODS}."
        )

    original = parse_grammar(text)
    transforms: List[str] = []
    grammar = original

    def _apply(label: str, transformer) -> None:
        nonlocal grammar
        new_grammar = transformer(grammar)
        if (
            new_grammar.start_symbol != grammar.start_symbol
            or new_grammar.productions != grammar.productions
        ):
            transforms.append(label)
        grammar = new_grammar

    if remove_useless:
        _apply("useless-symbol removal", remove_useless_symbols)
    if remove_left_recursion:
        _apply(
            "left-recursion removal",
            lambda g: apply_transforms(g, remove_left_recursion=True),
        )
    if left_factoring:
        _apply(
            "left factoring",
            lambda g: apply_transforms(g, left_factoring=True),
        )
    if remove_epsilon:
        _apply("ε-production removal", remove_epsilon_productions)
    if remove_unit:
        _apply("unit-production removal", remove_unit_productions)

    first = compute_first(grammar)
    follow = compute_follow(grammar, first)

    ll1_table = None
    conflicts = []
    if method in ("Predictive (LL(1))", "LL(1)"):
        ll1_table = build_ll1_table(grammar, first, follow)
        conflicts = ll1_table.conflicts

    result = TopDownResult(
        grammar=grammar,
        method=method,
        first=first,
        follow=follow,
        left_recursion=has_left_recursion(grammar),
        left_factoring=has_common_prefixes(grammar),
        ll1_table=ll1_table,
        conflicts=conflicts,
        transforms=transforms,
        stages=build_grammar_stages(original, grammar),
        original=original,
    )
    logger.info(
        "Top-down analysis (%s): left_recursion=%s, left_factoring=%s, conflicts=%d%s",
        method,
        result.left_recursion,
        result.left_factoring,
        len(conflicts),
        f", transforms: {', '.join(transforms)}" if transforms else "",
    )
    return result


def _reset(result: TopDownResult) -> None:
    result.steps = []
    result.derivation = []
    result.failed_attempts = []
    result.decision_points = []
    result.parse_tree = None
    result.accepted = False
    result.error = None


def _left_recursion_failure(result: TopDownResult, tokens: List[str]) -> None:
    _reset(result)
    result.steps = [
        TopDownStep(
            index=0,
            stack=[result.grammar.start_symbol],
            input_remaining=tokens + [END_MARKER],
            action="error",
            action_text="left recursion detected; cannot parse top-down",
            nonterminal=result.grammar.start_symbol,
        )
    ]
    result.error = LEFT_RECURSION_ERROR


def simulate_topdown(result: TopDownResult, input_string: str) -> TopDownResult:
    """Run a top-down parse for ``result`` against ``input_string``.

    Populates ``steps``, ``parse_tree``, ``accepted``, ``error``, ``derivation``,
    ``failed_attempts`` and ``decision_points`` on ``result`` and returns it.
    """
    grammar = result.grammar
    tokens = tokenize(input_string, grammar)
    _reset(result)

    if result.left_recursion:
        _left_recursion_failure(result, tokens)
        return result

    method = result.method
    if method in ("Recursive Descent", "Backtracking Recursive Descent"):
        parser_cls = (
            BacktrackingRecursiveDescentParser
            if method == "Backtracking Recursive Descent"
            else RecursiveDescentParser
        )
        parser = parser_cls(grammar, result.first, result.follow)
        accepted, tree, error = parser.parse(tokens)
        result.steps = parser.steps
        result.derivation = parser.derivation
        result.failed_attempts = parser.failed_attempts
        result.decision_points = parser.decision_points
        result.accepted = accepted
        result.parse_tree = tree
        result.error = error
        return result

    table = result.ll1_table
    if table is None:
        table = build_ll1_table(grammar, result.first, result.follow)
        result.ll1_table = table
        result.conflicts = table.conflicts
    outcome = parse_predictive(table, grammar, tokens)
    result.steps = outcome.steps
    result.derivation = outcome.derivation
    result.accepted = outcome.accepted
    result.parse_tree = outcome.tree
    result.error = outcome.error
    return result