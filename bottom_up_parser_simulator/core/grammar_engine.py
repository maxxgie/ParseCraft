"""Central grammar engine helpers shared by all parsers.

Provides grammar augmentation (``S' -> S``) and a small collection of
grammar-inspection utilities used across the parsing algorithms.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)

DEFAULT_AUGMENTED_START = "S'"


def production_order_map(grammar: Grammar) -> Dict[Tuple[str, Tuple[str, ...]], int]:
    """Return a mapping from ``(lhs, rhs)`` to its production index.

    The augmented production (when present) is index ``0``; user productions
    follow in declaration order. This is the numbering used by textbook
    presentations and by the ACTION table's ``Rx`` entries.

    Args:
        grammar: The (possibly augmented) grammar.

    Returns:
        A dict mapping ``(lhs, rhs_tuple)`` to a zero-based production index.
    """
    order: Dict[Tuple[str, Tuple[str, ...]], int] = {}
    index = 0
    for lhs, bodies in grammar.productions.items():
        for body in bodies:
            order[(lhs, tuple(body))] = index
            index += 1
    return order


def ordered_symbols(grammar: Grammar) -> List[str]:
    """Return every grammar symbol in order of first appearance.

    Symbols are collected left-to-right, top-to-bottom across the productions
    (left-hand sides included). The resulting order is used for transitions and
    table columns so that the output matches the order in which a human reads
    the grammar, rather than an arbitrary alphabetical sort.

    Args:
        grammar: The grammar to inspect.

    Returns:
        A list of symbols in first-appearance order, without duplicates.
    """
    seen: set[str] = set()
    ordered: List[str] = []
    for lhs, bodies in grammar.productions.items():
        for sym in [lhs, *(s for body in bodies for s in body)]:
            if sym == "ε" or sym in seen:
                continue
            seen.add(sym)
            ordered.append(sym)
    return ordered


def augment_grammar(
    grammar: Grammar, new_start: str = DEFAULT_AUGMENTED_START
) -> Grammar:
    """Return an augmented grammar with a fresh start symbol ``S' -> S``.

    Args:
        grammar: The original grammar.
        new_start: The preferred name for the augmented start symbol. If it
            collides with an existing non-terminal, primes are appended until a
            free name is found.

    Returns:
        A new :class:`Grammar` whose start symbol produces the original start.
    """
    name = new_start
    while name in grammar.non_terminals or name in grammar.terminals:
        name += "'"

    augmented_productions = {name: [[grammar.start_symbol]]}
    augmented_productions.update(grammar.productions)

    augmented = Grammar(
        start_symbol=name,
        productions=augmented_productions,
    )
    logger.debug("Augmented grammar with start symbol '%s'", name)
    return augmented


def used_symbols(grammar: Grammar) -> List[str]:
    """Return the sorted list of symbols appearing on any right-hand side."""
    seen = set()
    for bodies in grammar.productions.values():
        for body in bodies:
            seen.update(body)
    return sorted(seen)


def undefined_symbols(grammar: Grammar) -> List[str]:
    """Return symbols used but never defined as a non-terminal.

    A symbol is considered an undefined non-terminal when it looks like a
    non-terminal (an identifier beginning with an upper-case letter) yet has no
    productions of its own.
    """
    result = []
    for sym in used_symbols(grammar):
        if sym == "ε":
            continue
        if sym in grammar.non_terminals:
            continue
        if sym.isidentifier() and sym[:1].isupper():
            result.append(sym)
    return result