"""GOTO computation for LR automaton."""

from __future__ import annotations

from typing import Dict, Set, List

from core.logging_config import get_logger
from core.closure import closure
from models.lr_item import LRItem
from models.grammar import Grammar

logger = get_logger(__name__)


def goto(items: Set[LRItem], symbol: str, grammar: Grammar) -> Set[LRItem]:
    """Compute the GOTO of a set of LR items on a symbol.

    Args:
        items: Set of LR items.
        symbol: The symbol to transition on.
        grammar: The grammar.

    Returns:
        Closure of the set of items with the dot advanced past symbol.
    """
    new_items = set()

    for item in items:
        next_sym = item.next_symbol()
        if next_sym == symbol:
            new_items.add(item.advance_dot())

    if not new_items:
        return set()

    result = closure(new_items, grammar)
    logger.debug("GOTO on '%s' computed: %d items", symbol, len(result))
    return result