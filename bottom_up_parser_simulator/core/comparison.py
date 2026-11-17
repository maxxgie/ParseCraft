"""Parser comparison across LL(1) and the LR family.

Builds a side-by-side comparison of the supported parsing methods for a
grammar: number of states, table size, conflicts, and compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.engine import analyze
from core.grammar_parser import parse_grammar
from core.logging_config import get_logger
from core.topdown import analyze_topdown

logger = get_logger(__name__)

PARSER_ORDER = ["LL(1)", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]


@dataclass
class ParserStats:
    """Statistics for a single parsing method on a grammar.

    Attributes:
        parser: Parser name.
        num_states: Number of automaton states (``None`` for LL(1)).
        num_terminals: Count of terminals.
        num_nonterminals: Count of non-terminals.
        table_size: Number of table cells (rows x columns).
        conflicts: Number of conflicts detected.
        conflict_free: Whether the table is conflict-free.
        compatible: Whether the grammar can use this parser.
        notes: Explanatory notes.
    """

    parser: str
    num_states: Optional[int]
    num_terminals: int
    num_nonterminals: int
    table_size: int
    conflicts: int
    conflict_free: bool
    compatible: bool
    notes: List[str] = field(default_factory=list)

    def as_row(self) -> List[str]:
        """Return a display row for a table widget."""
        states = "-" if self.num_states is None else str(self.num_states)
        status = "compatible" if self.compatible else "not applicable"
        if not self.conflict_free:
            status = f"conflicts ({self.conflicts})"
        return [
            self.parser,
            states,
            str(self.table_size),
            str(self.conflicts),
            status,
            "; ".join(self.notes),
        ]


@dataclass
class ComparisonReport:
    """The comparison of all parsers for a grammar.

    Attributes:
        parser_stats: Per-parser statistics, in :data:`PARSER_ORDER`.
    """

    parser_stats: List[ParserStats] = field(default_factory=list)

    def summary(self) -> str:
        """Return a short human-readable summary."""
        applicable = [s.parser for s in self.parser_stats if s.compatible]
        conflict_free = [
            s.parser for s in self.parser_stats if s.conflict_free
        ]
        return (
            f"Compatible: {', '.join(applicable) or 'none'}. "
            f"Conflict-free: {', '.join(conflict_free) or 'none'}."
        )


def compare_parsers(text: str) -> ComparisonReport:
    """Compare LL(1) and the LR family for the grammar in ``text``.

    Args:
        text: Grammar text in BNF format.

    Returns:
        A :class:`ComparisonReport`.
    """
    grammar = parse_grammar(text)
    num_terminals = len(grammar.terminals)
    num_nonterminals = len(grammar.non_terminals)
    stats: List[ParserStats] = []

    # LL(1)
    try:
        ll1 = analyze_topdown(text, "LL(1)")
        notes: List[str] = []
        if ll1.left_recursion:
            notes.append("left recursion")
        if ll1.left_factoring:
            notes.append("needs left factoring")
        compatible = not ll1.conflicts and not ll1.left_recursion
        stats.append(
            ParserStats(
                parser="LL(1)",
                num_states=None,
                num_terminals=num_terminals,
                num_nonterminals=num_nonterminals,
                table_size=num_nonterminals * (num_terminals + 1),
                conflicts=len(ll1.conflicts),
                conflict_free=not ll1.conflicts,
                compatible=compatible,
                notes=notes,
            )
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("LL(1) comparison failed")
        stats.append(
            ParserStats(
                "LL(1)", None, num_terminals, num_nonterminals, 0, 0, False, False,
                ["analysis failed"],
            )
        )

    # LR family
    for parser_type in ["LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]:
        try:
            result = analyze(text, parser_type)
            num_states = len(result.automaton.states)
            conflicts = len(result.conflicts)
            notes = []
            if conflicts:
                notes.append("conflicts")
            stats.append(
                ParserStats(
                    parser=parser_type,
                    num_states=num_states,
                    num_terminals=num_terminals,
                    num_nonterminals=num_nonterminals,
                    table_size=num_states * (num_terminals + num_nonterminals),
                    conflicts=conflicts,
                    conflict_free=not conflicts,
                    compatible=True,
                    notes=notes,
                )
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("%s comparison failed", parser_type)
            stats.append(
                ParserStats(
                    parser_type, None, num_terminals, num_nonterminals, 0, 0,
                    False, False, ["analysis failed"],
                )
            )

    report = ComparisonReport(parser_stats=stats)
    logger.info("Parser comparison complete: %s", report.summary())
    return report