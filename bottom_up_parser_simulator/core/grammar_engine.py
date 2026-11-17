"""Central grammar engine helpers shared by all parsers.

Provides grammar augmentation (``S' -> S``) and a small collection of
grammar-inspection utilities used across the parsing algorithms.
"""

from __future__ import annotations

from typing import List

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)

DEFAULT_AUGMENTED_START = "S'"


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