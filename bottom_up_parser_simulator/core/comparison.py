"""Intelligent parser compatibility analysis.

For a given grammar this module decides, per supported parsing method, whether
the method can be used and *why*. It is the engine behind the "Grammar
Compatibility" tab: each row has a status and a short reason, and selecting a
row reveals a longer explanation suitable for teaching.

The analysis is deliberately mathematical:

* LL(1) is rejected when the grammar is left-recursive or has LL(1) conflicts.
* LR(0) is rejected when it has shift/reduce conflicts (it has no lookahead).
* SLR(1) is rejected when FOLLOW sets do not resolve the conflicts.
* CLR(1) is rejected only when the canonical LR(1) automaton has conflicts.
* LALR(1) is rejected when merging states introduces conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.engine import analyze
from core.grammar_parser import parse_grammar
from core.grammar_transform import has_common_prefixes
from core.logging_config import get_logger
from core.topdown import analyze_topdown
from models.grammar import Grammar

logger = get_logger(__name__)

PARSER_ORDER = ["LL(1)", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]

STATUS_COMPATIBLE = "compatible"
STATUS_INCOMPATIBLE = "not compatible"
STATUS_REVIEW = "analysis required"


def _direct_left_recursive(grammar: Grammar) -> List[str]:
    """Return non-terminals with a production starting with themselves."""
    result: List[str] = []
    for nt, bodies in grammar.productions.items():
        if any(body and body[0] == nt for body in bodies):
            result.append(nt)
    return result


def _left_recursive_symbols(grammar: Grammar) -> List[str]:
    """Return non-terminals that are directly or indirectly left-recursive."""
    edges: dict[str, set[str]] = {nt: set() for nt in grammar.non_terminals}
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            if body and body[0] in grammar.non_terminals:
                edges[nt].add(body[0])

    recursive: List[str] = []
    for start in grammar.non_terminals:
        stack = list(edges[start])
        seen: set[str] = set()
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


def _lr_reason(parser: str, conflicts: int) -> Tuple[str, str, str]:
    """Return ``(status, reason, explanation)`` for an LR-family parser."""
    if conflicts == 0:
        reasons = {
            "LR(0)": "No conflicts (grammar is LR(0))",
            "SLR(1)": "FOLLOW sets resolve all conflicts",
            "CLR(1)": "Canonical LR(1) lookahead resolves conflicts",
            "LALR(1)": "Merged states remain conflict-free",
        }
        explanations = {
            "LR(0)": (
                "The LR(0) automaton has no shift/reduce or reduce/reduce "
                "conflicts, so the grammar is LR(0)."
            ),
            "SLR(1)": (
                "SLR(1) uses FOLLOW sets as lookahead. Every ACTION cell is "
                "unambiguous, so the grammar is SLR(1)."
            ),
            "CLR(1)": (
                "The canonical LR(1) collection assigns precise lookaheads to "
                "each item, so every ACTION cell is unambiguous."
            ),
            "LALR(1)": (
                "Merging LR(1) states with identical cores did not introduce "
                "any conflict, so the grammar is LALR(1)."
            ),
        }
        return STATUS_COMPATIBLE, reasons[parser], explanations[parser]

    # There are conflicts.
    reasons = {
        "LR(0)": f"{conflicts} shift/reduce conflict(s) — no lookahead",
        "SLR(1)": f"{conflicts} conflict(s) — FOLLOW sets are insufficient",
        "CLR(1)": f"{conflicts} conflict(s) — canonical LR(1) is ambiguous",
        "LALR(1)": f"{conflicts} conflict(s) — merging lost lookahead",
    }
    explanations = {
        "LR(0)": (
            "LR(0) has no lookahead information. When the parser reaches a "
            "state with a completed item and a shift item, it cannot decide "
            "whether to reduce or shift. This is a property of the grammar, "
            "not a bug: use a parser with lookahead (SLR(1), CLR(1) or LALR(1))."
        ),
        "SLR(1)": (
            "SLR(1) approximates lookahead with FOLLOW sets. The conflicts "
            "mean the FOLLOW approximation is too coarse for this grammar. "
            "Use CLR(1) or LALR(1), which compute precise per-state lookaheads."
        ),
        "CLR(1)": (
            "The canonical LR(1) automaton itself has a conflict, so the "
            "grammar is not LR(1). Investigate the grammar (it may be "
            "ambiguous); no conflict-free LR parser exists for it."
        ),
        "LALR(1)": (
            "LALR(1) merges states with the same LR(0) core. The merge "
            "combined lookaheads that were distinct in the canonical LR(1) "
            "automaton, creating a conflict. CLR(1) avoids the merge and is "
            "conflict-free."
        ),
    }
    return STATUS_INCOMPATIBLE, reasons[parser], explanations[parser]


@dataclass
class ParserStats:
    """Compatibility statistics for a single parsing method.

    Attributes:
        parser: Parser name.
        num_states: Number of automaton states (``None`` for LL(1)).
        num_terminals: Count of terminals.
        num_nonterminals: Count of non-terminals.
        table_size: Number of table cells (rows x columns).
        conflicts: Number of conflicts detected.
        conflict_free: Whether the table is conflict-free.
        compatible: Whether the grammar can use this parser.
        status: Short display status (``compatible``, ``not compatible`` or
            ``analysis required``).
        reason: One-line reason shown in the compatibility table.
        explanation: Longer teaching explanation shown when a row is selected.
        notes: Additional notes (kept for backward compatibility).
    """

    parser: str
    num_states: Optional[int]
    num_terminals: int
    num_nonterminals: int
    table_size: int
    conflicts: int
    conflict_free: bool
    compatible: bool
    status: str = ""
    reason: str = ""
    explanation: str = ""
    notes: List[str] = field(default_factory=list)

    def as_row(self) -> List[str]:
        """Return ``[Parser, Status, Reason]`` for a table widget."""
        return [self.parser, self.status, self.reason]


@dataclass
class ComparisonReport:
    """The compatibility comparison of all parsers for a grammar.

    Attributes:
        parser_stats: Per-parser statistics, in :data:`PARSER_ORDER`.
        suggested: The recommended parser, when one is compatible.
        grammar_text: The grammar the comparison was computed for.
        grammar: The parsed grammar object (used for expanded display).
    """

    parser_stats: List[ParserStats] = field(default_factory=list)
    suggested: Optional[str] = None
    grammar_text: str = ""
    grammar: Optional[Grammar] = None

    def summary(self) -> str:
        """Return a short human-readable summary."""
        applicable = [s.parser for s in self.parser_stats if s.compatible]
        conflict_free = [s.parser for s in self.parser_stats if s.conflict_free]
        suggestion = f" Recommended: {self.suggested}." if self.suggested else ""
        return (
            f"Compatible: {', '.join(applicable) or 'none'}. "
            f"Conflict-free: {', '.join(conflict_free) or 'none'}.{suggestion}"
        )


def _ll1_stats(
    grammar: Grammar,
    text: str,
    num_terminals: int,
    num_nonterminals: int,
) -> ParserStats:
    """Build the LL(1) compatibility entry with a detailed reason."""
    try:
        result = analyze_topdown(text, "LL(1)")
        direct = _direct_left_recursive(grammar)
        indirect = [s for s in _left_recursive_symbols(grammar) if s not in direct]
        conflicts = result.conflicts
        common = has_common_prefixes(grammar)
        table_size = num_nonterminals * (num_terminals + 1)

        if direct:
            status = STATUS_INCOMPATIBLE
            reason = "Direct left recursion detected"
            explanation = (
                "Recursive-descent and LL(1) parsers expand the leftmost "
                "non-terminal first. A production such as "
                f"'{direct[0]} -> {direct[0]} ...' immediately calls itself "
                "without consuming input, so the parser recurses forever. "
                "Remove left recursion before using a top-down parser."
            )
        elif indirect:
            status = STATUS_INCOMPATIBLE
            reason = "Indirect left recursion detected"
            explanation = (
                "Left recursion through other non-terminals ("
                + ", ".join(indirect)
                + ") also makes recursive descent loop. Remove it before "
                "using a top-down parser."
            )
        elif conflicts:
            status = STATUS_INCOMPATIBLE
            reason = f"{len(conflicts)} LL(1) conflict(s)"
            kinds: set[str] = set()
            for conflict in conflicts:
                for body in conflict.productions:
                    if not body:
                        kinds.add("FIRST/FOLLOW")
                    else:
                        kinds.add("FIRST/FIRST")
            explanation = (
                "The LL(1) table has multiply-defined cells ("
                + ", ".join(sorted(kinds))
                + "). The parser cannot choose a single production from the "
                "lookahead alone. Left factoring may help for FIRST/FIRST "
                "conflicts; otherwise use an LR parser."
            )
        else:
            status = STATUS_COMPATIBLE
            reason = "No conflicts (grammar is LL(1))"
            explanation = (
                "The predictive table has exactly one production per cell, so "
                "LL(1) and recursive descent can parse the grammar with a "
                "single token of lookahead."
            )

        notes: List[str] = []
        if common:
            notes.append("left factoring advised")
        return ParserStats(
            parser="LL(1)",
            num_states=None,
            num_terminals=num_terminals,
            num_nonterminals=num_nonterminals,
            table_size=table_size,
            conflicts=len(conflicts),
            conflict_free=not conflicts,
            compatible=status == STATUS_COMPATIBLE,
            status=status,
            reason=reason,
            explanation=explanation,
            notes=notes,
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("LL(1) comparison failed")
        return ParserStats(
            parser="LL(1)",
            num_states=None,
            num_terminals=num_terminals,
            num_nonterminals=num_nonterminals,
            table_size=0,
            conflicts=0,
            conflict_free=False,
            compatible=False,
            status=STATUS_INCOMPATIBLE,
            reason="Analysis failed",
            explanation="The LL(1) analysis could not be completed.",
        )


def compare_parsers(text: str) -> ComparisonReport:
    """Compare LL(1) and the LR family for the grammar in ``text``.

    Args:
        text: Grammar text in BNF format.

    Returns:
        A :class:`ComparisonReport` with a status, reason and explanation per
        parser, plus the recommended parser.
    """
    grammar = parse_grammar(text)
    num_terminals = len(grammar.terminals)
    num_nonterminals = len(grammar.non_terminals)
    stats: List[ParserStats] = [_ll1_stats(grammar, text, num_terminals, num_nonterminals)]

    for parser_type in ["LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]:
        try:
            result = analyze(text, parser_type)
            num_states = len(result.automaton.states)
            conflicts = len(result.conflicts)
            status, reason, explanation = _lr_reason(parser_type, conflicts)
            stats.append(
                ParserStats(
                    parser=parser_type,
                    num_states=num_states,
                    num_terminals=num_terminals,
                    num_nonterminals=num_nonterminals,
                    table_size=num_states * (num_terminals + num_nonterminals),
                    conflicts=conflicts,
                    conflict_free=not conflicts,
                    compatible=status == STATUS_COMPATIBLE,
                    status=status,
                    reason=reason,
                    explanation=explanation,
                    notes=[] if not conflicts else ["conflicts"],
                )
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("%s comparison failed", parser_type)
            stats.append(
                ParserStats(
                    parser=parser_type,
                    num_states=None,
                    num_terminals=num_terminals,
                    num_nonterminals=num_nonterminals,
                    table_size=0,
                    conflicts=0,
                    conflict_free=False,
                    compatible=False,
                    status=STATUS_INCOMPATIBLE,
                    reason="Analysis failed",
                    explanation="The automaton could not be constructed.",
                )
            )

    suggested = _recommend(stats)
    report = ComparisonReport(
        parser_stats=stats,
        suggested=suggested,
        grammar_text=grammar.to_text(),
        grammar=grammar,
    )
    logger.info("Parser compatibility complete: %s", report.summary())
    return report


def _recommend(stats: List[ParserStats]) -> Optional[str]:
    """Pick a recommended parser.

    Preference order favours the most practical conflict-free method:
    LALR(1) (compact), then SLR(1), CLR(1), LR(0), then LL(1).
    """
    order = ["LALR(1)", "SLR(1)", "CLR(1)", "LR(0)", "LL(1)"]
    by_name = {s.parser: s for s in stats}
    for name in order:
        entry = by_name.get(name)
        if entry is not None and entry.compatible and entry.conflict_free:
            return name
    return None