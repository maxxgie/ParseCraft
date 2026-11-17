"""GOTO computation for LR automaton construction.

``GOTO(I, X)`` advances the dot over ``X`` in every item of ``I`` whose next
symbol is ``X``, then takes the closure of the resulting set.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from core.closure import closure, closure_with_trace
from core.logging_config import get_logger
from models.grammar import Grammar
from models.lr_item import LRItem

logger = get_logger(__name__)


def _sort_items(items: Set[LRItem]) -> List[LRItem]:
    """Return items in a stable, human-readable order."""
    return sorted(
        items, key=lambda item: (item.lhs, item.rhs, item.dot, item.lookahead)
    )


def goto(items: Set[LRItem], symbol: str, grammar: Grammar) -> Set[LRItem]:
    """Compute the GOTO of a set of LR items on a symbol.

    Args:
        items: Set of LR items.
        symbol: The symbol to transition on.
        grammar: The grammar.

    Returns:
        Closure of the set of items with the dot advanced past ``symbol``.
    """
    moved: Set[LRItem] = set()
    for item in items:
        if item.next_symbol() == symbol:
            moved.add(item.advance_dot())

    if not moved:
        return set()

    result = closure(moved, grammar)
    logger.debug("GOTO on '%s' computed: %d items", symbol, len(result))
    return result


def goto_with_trace(
    items: Set[LRItem], symbol: str, grammar: Grammar
) -> Tuple[Set[LRItem], Dict[str, object]]:
    """Compute GOTO and return a step-by-step trace.

    Args:
        items: The current item set.
        symbol: The grammar symbol to advance over.
        grammar: The grammar.

    Returns:
        ``(result, trace)`` where ``trace`` contains:

        * ``symbol``: the symbol advanced over;
        * ``moved``: the items whose dot moved (before closure);
        * ``closure_steps``: the trace returned by
          :func:`core.closure.closure_with_trace`.
    """
    moved_list: List[LRItem] = []
    moved_set: Set[LRItem] = set()
    for item in _sort_items(items):
        if item.next_symbol() != symbol:
            continue
        advanced = item.advance_dot()
        if advanced not in moved_set:
            moved_set.add(advanced)
            moved_list.append(advanced)

    if not moved_list:
        return set(), {
            "symbol": symbol,
            "moved": [],
            "closure_steps": [],
        }

    result, closure_steps = closure_with_trace(moved_set, grammar)
    return result, {
        "symbol": symbol,
        "moved": moved_list,
        "closure_steps": closure_steps,
    }