"""LR(0) parsing table generator (thin wrapper over table_builder)."""

from __future__ import annotations

from core.automaton import LRAutomaton
from core.logging_config import get_logger
from core.table_builder import build_parsing_table
from models.grammar import Grammar
from models.parsing_table import ParseTable

logger = get_logger(__name__)


def generate_lr0_table(automaton: LRAutomaton, grammar: Grammar) -> ParseTable:
    """Generate an LR(0) parsing table.

    Args:
        automaton: The LR(0) automaton.
        grammar: The original grammar.

    Returns:
        A :class:`ParseTable` with ACTION and GOTO entries.
    """
    table, conflicts = build_parsing_table(automaton, grammar, "lr0")
    return table