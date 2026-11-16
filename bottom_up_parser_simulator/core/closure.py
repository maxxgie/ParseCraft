"""LR item closure computation."""

from __future__ import annotations

from typing import Set, List

from core.logging_config import get_logger
from models.lr_item import LRItem
from models.grammar import Grammar

logger = get_logger(__name__)


def closure(items: Set[LRItem], grammar: Grammar) -> Set[LRItem]:
    """Compute the closure of a set of LR items.

    Args:
        items: Initial set of LR items.
        grammar: The grammar.

    Returns:
        Closure of the item set.
    """
    closure_set = set(items)
    changed = True

    while changed:
        changed = False
        new_items = set()

        for item in closure_set:
            next_sym = item.next_symbol()
            if next_sym is None or next_sym not in grammar.non_terminals:
                continue

            # For each production of next_sym, add new items
            for rhs in grammar.get_productions_for(next_sym):
                # For LR(0), lookahead is empty
                new_item = LRItem(lhs=next_sym, rhs=tuple(rhs), dot=0, lookahead=item.lookahead)
                if new_item not in closure_set:
                    new_items.add(new_item)
                    changed = True

        closure_set.update(new_items)

    logger.debug("Closure computed: %d items", len(closure_set))
    return closure_set