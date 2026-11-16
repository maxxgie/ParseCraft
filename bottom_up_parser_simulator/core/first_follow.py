"""FIRST and FOLLOW set computation."""

from __future__ import annotations

from typing import Dict, Set

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)


def compute_first(grammar: Grammar) -> Dict[str, Set[str]]:
    """Compute FIRST sets for all symbols in the grammar.

    Args:
        grammar: The grammar to compute FIRST sets for.

    Returns:
        Dictionary mapping each symbol to its FIRST set.
    """
    first: Dict[str, Set[str]] = {}

    # Initialize FIRST sets
    for terminal in grammar.terminals:
        first[terminal] = {terminal}
    first["ε"] = {"ε"}

    for non_terminal in grammar.non_terminals:
        first[non_terminal] = set()

    # Compute FIRST sets iteratively
    changed = True
    while changed:
        changed = False
        for nt, rhs_list in grammar.productions.items():
            for rhs in rhs_list:
                if not rhs:
                    # Empty production: add ε to FIRST(nt)
                    if "ε" not in first[nt]:
                        first[nt].add("ε")
                        changed = True
                    continue

                # Compute FIRST for the production body
                all_derive_epsilon = True
                for sym in rhs:
                    if sym == "ε":
                        if "ε" not in first[nt]:
                            first[nt].add("ε")
                            changed = True
                        break

                    # Add FIRST(sym) - {ε} to FIRST(nt)
                    for s in first.get(sym, set()):
                        if s != "ε" and s not in first[nt]:
                            first[nt].add(s)
                            changed = True

                    # If ε not in FIRST(sym), stop
                    if "ε" not in first.get(sym, set()):
                        all_derive_epsilon = False
                        break

                # If all symbols can derive ε, add ε to FIRST(nt)
                if all_derive_epsilon:
                    if "ε" not in first[nt]:
                        first[nt].add("ε")
                        changed = True

    logger.info("FIRST sets computed for %d symbols", len(first))
    return first


def compute_follow(grammar: Grammar, first: Dict[str, Set[str]] | None = None) -> Dict[str, Set[str]]:
    """Compute FOLLOW sets for all non-terminals.

    Args:
        grammar: The grammar to compute FOLLOW sets for.
        first: Pre-computed FIRST sets. If None, they will be computed.

    Returns:
        Dictionary mapping each non-terminal to its FOLLOW set.
    """
    if first is None:
        first = compute_first(grammar)

    follow: Dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}

    # Add end marker to FOLLOW of start symbol
    follow[grammar.start_symbol].add("$")

    # Compute FOLLOW sets iteratively
    changed = True
    while changed:
        changed = False
        for nt, rhs_list in grammar.productions.items():
            for rhs in rhs_list:
                for i, sym in enumerate(rhs):
                    if sym not in grammar.non_terminals:
                        continue

                    # Add FIRST of the rest of the production to FOLLOW(sym)
                    rest = rhs[i + 1:]
                    if rest:
                        first_of_rest = set()
                        all_derive_epsilon = True
                        for s in rest:
                            first_of_rest.update(first.get(s, set()) - {"ε"})
                            if "ε" not in first.get(s, set()):
                                all_derive_epsilon = False
                                break

                        for s in first_of_rest:
                            if s not in follow[sym]:
                                follow[sym].add(s)
                                changed = True

                        # If rest can derive ε, add FOLLOW(nt) to FOLLOW(sym)
                        if all_derive_epsilon:
                            for s in follow.get(nt, set()):
                                if s not in follow[sym]:
                                    follow[sym].add(s)
                                    changed = True
                    else:
                        # sym is at the end, add FOLLOW(nt) to FOLLOW(sym)
                        for s in follow.get(nt, set()):
                            if s not in follow[sym]:
                                follow[sym].add(s)
                                changed = True

    logger.info("FOLLOW sets computed for %d non-terminals", len(follow))
    return follow


def compute_first_of_string(
    symbols: List[str], first: Dict[str, Set[str]]
) -> Set[str]:
    """Compute FIRST set for a string of symbols.

    Args:
        symbols: List of grammar symbols.
        first: Pre-computed FIRST sets.

    Returns:
        FIRST set of the string.
    """
    result = set()
    all_derive_epsilon = True

    for sym in symbols:
        if sym == "ε":
            continue

        result.update(first.get(sym, set()) - {"ε"})

        if "ε" not in first.get(sym, set()):
            all_derive_epsilon = False
            break

    if all_derive_epsilon:
        result.add("ε")

    return result