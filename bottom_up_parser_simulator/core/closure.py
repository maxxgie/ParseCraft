"""LR item closure computation.

The closure operation is the heart of LR automaton construction: given a set of
items, repeatedly add ``B -> •γ`` for every item ``A -> α • B β`` whose next
symbol ``B`` is a non-terminal, until no new items appear.

Two entry points are provided:

* :func:`closure` returns only the final item set (fast path used by the
  automaton builder).
* :func:`closure_with_trace` returns the final set together with a
  deterministic, teaching-oriented trace of every item that was added.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from core.logging_config import get_logger
from models.grammar import Grammar
from models.lr_item import LRItem

logger = get_logger(__name__)

# A trace step is a dict:
#   {"kind": "seed", "items": [...]}                  initial items
#   {"kind": "add", "from": item, "symbol": B, "item": new_item}
TraceStep = Dict[str, object]


def _closure_impl(
    items: Set[LRItem], grammar: Grammar, record: bool
) -> Tuple[Set[LRItem], List[TraceStep]]:
    """Shared ordered closure implementation.

    Items are processed in insertion order (breadth-first), so the trace is
    deterministic and mirrors how a human writes the closure by hand.
    """
    result: Set[LRItem] = set(items)
    ordered: List[LRItem] = list(items)
    steps: List[TraceStep] = []
    if record:
        steps.append({"kind": "seed", "items": list(ordered)})

    index = 0
    while index < len(ordered):
        item = ordered[index]
        index += 1

        next_sym = item.next_symbol()
        if next_sym is None or next_sym not in grammar.non_terminals:
            continue

        for rhs in grammar.get_productions_for(next_sym):
            new_item = LRItem(
                lhs=next_sym, rhs=tuple(rhs), dot=0, lookahead=item.lookahead
            )
            if new_item in result:
                continue
            result.add(new_item)
            ordered.append(new_item)
            if record:
                steps.append(
                    {
                        "kind": "add",
                        "from": item,
                        "symbol": next_sym,
                        "item": new_item,
                    }
                )

    return result, steps


def closure(items: Set[LRItem], grammar: Grammar) -> Set[LRItem]:
    """Compute the closure of a set of LR items.

    Args:
        items: Initial set of LR items.
        grammar: The grammar.

    Returns:
        Closure of the item set.
    """
    result, _ = _closure_impl(items, grammar, record=False)
    logger.debug("Closure computed: %d items", len(result))
    return result


def closure_with_trace(
    items: Set[LRItem], grammar: Grammar
) -> Tuple[Set[LRItem], List[TraceStep]]:
    """Compute the closure and return a step-by-step trace.

    Args:
        items: Initial (seed) set of LR items.
        grammar: The grammar.

    Returns:
        ``(closure_set, steps)`` where ``steps`` records the seed and each
        added item, in a deterministic order suitable for display.
    """
    result, steps = _closure_impl(items, grammar, record=True)
    logger.debug("Closure computed with trace: %d items", len(result))
    return result, steps