"""Grammar analysis: validation, undefined symbols, duplicates, ambiguity,
left recursion, and left factoring checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from core.first_follow import compute_first, compute_follow
from core.grammar_engine import undefined_symbols
from core.grammar_transform import has_common_prefixes
from core.logging_config import get_logger
from core.topdown.ll1 import build_ll1_table
from models.grammar import Grammar

logger = get_logger(__name__)

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class GrammarIssue:
    """A single grammar analysis finding.

    Attributes:
        level: One of ``error``, ``warning``, ``info``.
        code: Machine-readable identifier.
        message: Human-readable description.
        symbols: Symbols involved in the finding.
    """

    level: str
    code: str
    message: str
    symbols: List[str] = field(default_factory=list)


@dataclass
class GrammarReport:
    """The full analysis of a grammar.

    Attributes:
        issues: All findings, ordered by severity.
    """

    issues: List[GrammarIssue] = field(default_factory=list)

    def _by_level(self, level: str) -> List[GrammarIssue]:
        return [i for i in self.issues if i.level == level]

    @property
    def errors(self) -> List[GrammarIssue]:
        return self._by_level(ERROR)

    @property
    def warnings(self) -> List[GrammarIssue]:
        return self._by_level(WARNING)

    @property
    def infos(self) -> List[GrammarIssue]:
        return self._by_level(INFO)

    @property
    def is_ok(self) -> bool:
        """Return ``True`` when there are no error-level issues."""
        return not self.errors

    def summary(self) -> str:
        """Return a one-line summary of the findings."""
        return (
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s), "
            f"{len(self.infos)} note(s)"
        )


def _left_recursive_symbols(grammar: Grammar) -> List[str]:
    """Return non-terminals that are directly or indirectly left-recursive."""
    edges: dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            if body and body[0] in grammar.non_terminals:
                edges[nt].add(body[0])

    # A symbol is left-recursive if it can reach itself through these edges.
    recursive: List[str] = []
    for start in grammar.non_terminals:
        stack = list(edges[start])
        seen: Set[str] = set()
        found = False
        while stack:
            node = stack.pop()
            if node == start:
                found = True
                break
            if node in seen:
                continue
            seen.add(node)
            stack.extend(edges.get(node, set()))
        if found:
            recursive.append(start)
    return recursive


def _unit_cycle_symbols(grammar: Grammar) -> List[str]:
    """Return non-terminals that participate in a unit-production cycle."""
    edges: dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            if len(body) == 1 and body[0] in grammar.non_terminals:
                edges[nt].add(body[0])

    cyclic: List[str] = []
    for start in grammar.non_terminals:
        stack = list(edges[start])
        seen: Set[str] = set()
        while stack:
            node = stack.pop()
            if node == start:
                cyclic.append(start)
                break
            if node in seen:
                continue
            seen.add(node)
            stack.extend(edges.get(node, set()))
    return cyclic


def _nullable_symbols(grammar: Grammar) -> Set[str]:
    """Return non-terminals that can derive the empty string.

    A body derives ``ε`` only when it is empty or every symbol in it is a
    nullable non-terminal. Terminals are never nullable.
    """
    nullable: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nt, bodies in grammar.productions.items():
            if nt in nullable:
                continue
            for body in bodies:
                if not body or all(sym in nullable for sym in body):
                    nullable.add(nt)
                    changed = True
                    break
    return nullable


def _direct_left_recursive(grammar: Grammar) -> List[str]:
    """Return non-terminals with a production that starts with themselves."""
    result: List[str] = []
    for nt, bodies in grammar.productions.items():
        if any(body and body[0] == nt for body in bodies):
            result.append(nt)
    return result


def _duplicate_productions(grammar: Grammar) -> List[GrammarIssue]:
    issues: List[GrammarIssue] = []
    reported: Set[str] = set()

    # Duplicates collected while parsing (kept out of the productions).
    for text in grammar.duplicates:
        if text in reported:
            continue
        reported.add(text)
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="duplicate_production",
                message=f"Duplicate production detected: {text}",
            )
        )

    # Duplicates in a programmatically-built grammar.
    for nt, bodies in grammar.productions.items():
        seen = set()
        for body in bodies:
            key = tuple(body)
            if key in seen:
                text = f"{nt} -> {' '.join(body) if body else 'ε'}"
                if text not in reported:
                    reported.add(text)
                    issues.append(
                        GrammarIssue(
                            level=WARNING,
                            code="duplicate_production",
                            message=f"Duplicate production detected: {text}",
                            symbols=[nt],
                        )
                    )
            seen.add(key)
    return issues


def analyze_grammar(
    grammar: Grammar, terminals: Optional[Set[str]] = None
) -> GrammarReport:
    """Analyze ``grammar`` and return a structured report.

    Args:
        grammar: The grammar to analyze.
        terminals: Optional declared terminal set. When provided, any symbol
            used on a right-hand side that is neither a non-terminal nor a
            declared terminal is reported as undefined.

    Returns:
        A :class:`GrammarReport`.
    """
    issues: List[GrammarIssue] = []

    # Structural checks.
    if not grammar.productions:
        issues.append(
            GrammarIssue(
                level=ERROR,
                code="empty_grammar",
                message="The grammar has no productions.",
            )
        )
    elif grammar.start_symbol not in grammar.productions:
        issues.append(
            GrammarIssue(
                level=ERROR,
                code="missing_start_production",
                message=(
                    f"Start symbol '{grammar.start_symbol}' has no productions."
                ),
                symbols=[grammar.start_symbol],
            )
        )

    # Duplicate productions.
    issues.extend(_duplicate_productions(grammar))

    # Undefined non-terminals.
    undefined: Set[str] = set()
    if terminals is not None:
        used: Set[str] = set()
        for bodies in grammar.productions.values():
            for body in bodies:
                used.update(body)
        undefined.update(used - grammar.non_terminals - set(terminals) - {"ε"})
    # Heuristic: an upper-case identifier used but never defined is treated as
    # an undefined non-terminal (terminals like ``id`` or ``+`` are ignored).
    for sym in undefined_symbols(grammar):
        if terminals is None or sym not in terminals:
            undefined.add(sym)
    if undefined:
        ordered = sorted(undefined)
        issues.append(
            GrammarIssue(
                level=ERROR,
                code="undefined_nonterminal",
                message=(
                    "Undefined non-terminal(s): "
                    + ", ".join(ordered)
                    + " — used but never defined."
                ),
                symbols=ordered,
            )
        )

    # Unreachable non-terminals.
    reachable: Set[str] = {grammar.start_symbol}
    changed = True
    while changed:
        changed = False
        for nt in list(reachable):
            for body in grammar.productions.get(nt, []):
                for sym in body:
                    if sym in grammar.non_terminals and sym not in reachable:
                        reachable.add(sym)
                        changed = True
    for nt in sorted(grammar.non_terminals - reachable):
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="unreachable",
                message=f"Non-terminal '{nt}' is unreachable from start symbol",
                symbols=[nt],
            )
        )

    # Non-productive non-terminals.
    productive: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nt, bodies in grammar.productions.items():
            if nt in productive:
                continue
            for body in bodies:
                if all(
                    sym in productive or sym in grammar.terminals for sym in body
                ):
                    productive.add(nt)
                    changed = True
                    break
    for nt in sorted(grammar.non_terminals - productive):
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="non_productive",
                message=(
                    f"Non-terminal '{nt}' is non-productive "
                    "(cannot derive a terminal string)"
                ),
                symbols=[nt],
            )
        )

    # Unit-production cycles.
    cycles = _unit_cycle_symbols(grammar)
    if cycles:
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="unit_cycle",
                message="Unit-production cycle involving: " + ", ".join(cycles),
                symbols=cycles,
            )
        )

    # Left recursion (split into direct and indirect for teaching clarity).
    direct_recursive = _direct_left_recursive(grammar)
    all_recursive = _left_recursive_symbols(grammar)
    indirect_recursive = [s for s in all_recursive if s not in direct_recursive]
    if direct_recursive:
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="direct_left_recursion",
                message=(
                    "Direct left recursion detected in: "
                    + ", ".join(direct_recursive)
                    + ". A recursive-descent parser would loop forever; remove "
                    "it before using a top-down parser."
                ),
                symbols=direct_recursive,
            )
        )
    if indirect_recursive:
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="indirect_left_recursion",
                message=(
                    "Indirect left recursion detected in: "
                    + ", ".join(indirect_recursive)
                    + ". Remove it before using a top-down parser."
                ),
                symbols=indirect_recursive,
            )
        )

    # Left factoring.
    if has_common_prefixes(grammar):
        issues.append(
            GrammarIssue(
                level=WARNING,
                code="left_factoring",
                message=(
                    "Common prefixes detected; left factoring is recommended "
                    "for predictive (LL(1)) parsing."
                ),
            )
        )

    # Nullable non-terminals.
    nullable = _nullable_symbols(grammar)
    if nullable:
        issues.append(
            GrammarIssue(
                level=INFO,
                code="nullable",
                message=(
                    "Nullable non-terminal(s) (can derive ε): "
                    + ", ".join(sorted(nullable))
                ),
                symbols=sorted(nullable),
            )
        )

    # LL(1) conflicts, classified as FIRST/FIRST or FIRST/FOLLOW.
    first = compute_first(grammar)
    follow = compute_follow(grammar, first)
    try:
        table = build_ll1_table(grammar, first, follow)
        for conflict in table.conflicts:
            has_epsilon = any(not body for body in conflict.productions)
            if has_epsilon:
                code = "first_follow_conflict"
                kind = "FIRST/FOLLOW"
            else:
                code = "first_first_conflict"
                kind = "FIRST/FIRST"
            issues.append(
                GrammarIssue(
                    level=WARNING,
                    code=code,
                    message=(
                        f"{kind} conflict: {conflict.message()} "
                        "(grammar is not LL(1))"
                    ),
                    symbols=[conflict.nonterminal, conflict.terminal],
                )
            )
    except Exception:  # pragma: no cover - analysis is best-effort
        logger.exception("LL(1) conflict analysis failed")

    # Ambiguity signal: reduce/reduce conflicts in the LR(0) automaton mean the
    # grammar may derive the same string in two ways.
    try:
        from core.automaton import LRAutomaton
        from core.table_builder import build_parsing_table

        lr0 = LRAutomaton(grammar)
        _, lr0_conflicts = build_parsing_table(lr0, grammar, "lr0", follow)
        reduce_reduce = [
            c for c in lr0_conflicts if c.conflict_type == "reduce-reduce"
        ]
        if reduce_reduce:
            issues.append(
                GrammarIssue(
                    level=WARNING,
                    code="ambiguous",
                    message=(
                        "Possible ambiguity: the LR(0) automaton has "
                        f"{len(reduce_reduce)} reduce-reduce conflict(s). "
                        "The same input may have two parse trees; verify with "
                        "CLR(1) or rewrite the grammar."
                    ),
                )
            )
    except Exception:  # pragma: no cover - analysis is best-effort
        logger.exception("Ambiguity analysis failed")

    issues.sort(key=lambda i: {ERROR: 0, WARNING: 1, INFO: 2}[i.level])
    logger.info("Grammar analysis complete: %s", GrammarReport(issues).summary())
    return GrammarReport(issues)