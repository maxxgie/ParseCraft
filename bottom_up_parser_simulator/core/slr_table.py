"""SLR(1) parsing table generator (thin wrapper over table_builder)."""

from __future__ import annotations

from core.automaton import LRAutomaton
from core.first_follow import compute_follow
from core.logging_config import get_logger
from core.table_builder import build_parsing_table
from models.grammar import Grammar
from models.parsing_table import ParseTable

logger = get_logger(__name__)


def generate_slr1_table(automaton: LRAutomaton, grammar: Grammar) -> ParseTable:
    """Generate an SLR(1) parsing table.

    Args:
        automaton: The LR(0) automaton (shared item sets).
        grammar: The original grammar.

    Returns:
        A :class:`ParseTable` with ACTION and GOTO entries.
    """
    follow = compute_follow(grammar)
    table, conflicts = build_parsing_table(automaton, grammar, "slr1", follow)
    return table