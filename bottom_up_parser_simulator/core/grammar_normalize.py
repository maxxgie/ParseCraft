"""Grammar normalisation passes.

Complements :mod:`core.grammar_transform` (left-recursion removal and left
factoring) with the classic normalisation algorithms used in compiler
construction:

* :func:`remove_useless_symbols` - drop non-generating and unreachable
  non-terminals;
* :func:`remove_epsilon_productions` - eliminate ``A -> ε`` while preserving
  the language (except possibly the empty string, which is preserved via a
  fresh start symbol);
* :func:`remove_unit_productions` - eliminate ``A -> B`` chains.

:func:`normalize_grammar` applies any requested subset in a sensible order.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Set

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)

EPSILON = "ε"
AUGMENTED_START = "S'"


def _dedupe(bodies: List[List[str]]) -> List[List[str]]:
    """Remove duplicate production bodies, preserving order."""
    seen: Set[tuple] = set()
    result: List[List[str]] = []
    for body in bodies:
        key = tuple(body)
        if key in seen:
            continue
        seen.add(key)
        result.append(list(body))
    return result


def _productive(grammar: Grammar) -> Set[str]:
    """Return non-terminals that can derive a (possibly empty) terminal string."""
    productive: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nt, bodies in grammar.productions.items():
            if nt in productive:
                continue
            for body in bodies:
                if all(
                    sym == EPSILON
                    or sym in grammar.terminals
                    or sym in productive
                    for sym in body
                ):
                    productive.add(nt)
                    changed = True
                    break
    return productive


def _nullable(grammar: Grammar) -> Set[str]:
    """Return non-terminals that can derive the empty string."""
    nullable: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nt, bodies in grammar.productions.items():
            if nt in nullable:
                continue
            for body in bodies:
                if all(sym == EPSILON or sym in nullable for sym in body):
                    nullable.add(nt)
                    changed = True
                    break
    return nullable


def _fresh_name_factory(grammar: Grammar):
    """Return a ``fresh(base)`` callable avoiding collisions (incl. ``S'``)."""
    used: Set[str] = set(grammar.non_terminals) | set(grammar.terminals)

    def fresh(base: str) -> str:
        name = base + "'"
        while name in used or name == AUGMENTED_START:
            name += "'"
        used.add(name)
        return name

    return fresh


# ----------------------------------------------------------------------
# Availability checks
# ----------------------------------------------------------------------
def has_epsilon_productions(grammar: Grammar) -> bool:
    """Return ``True`` if any production has an empty body."""
    return any(not body for bodies in grammar.productions.values() for body in bodies)


def has_unit_productions(grammar: Grammar) -> bool:
    """Return ``True`` if any production is a unit production ``A -> B``."""
    for bodies in grammar.productions.values():
        for body in bodies:
            if len(body) == 1 and body[0] in grammar.non_terminals:
                return True
    return False


def has_useless_symbols(grammar: Grammar) -> bool:
    """Return ``True`` if the grammar has unreachable or non-generating symbols."""
    productive = _productive(grammar)

    # Non-generating non-terminals (excluding the start symbol).
    for nt in grammar.non_terminals:
        if nt != grammar.start_symbol and nt not in productive:
            return True

    # Unreachable non-terminals.
    reachable: Set[str] = set()
    stack = [grammar.start_symbol]
    while stack:
        nt = stack.pop()
        if nt in reachable:
            continue
        reachable.add(nt)
        for body in grammar.productions.get(nt, []):
            for sym in body:
                if sym in grammar.non_terminals and sym not in reachable:
                    stack.append(sym)
    return bool(grammar.non_terminals - reachable)


# ----------------------------------------------------------------------
# Transformations
# ----------------------------------------------------------------------
def remove_useless_symbols(grammar: Grammar) -> Grammar:
    """Remove non-generating and unreachable non-terminals.

    Args:
        grammar: The grammar to clean up.

    Returns:
        A new :class:`Grammar`.
    """
    productive = _productive(grammar)

    # Step 1: drop non-generating non-terminals and any production mentioning
    # a symbol that can never be rewritten to terminals.
    productions: Dict[str, List[List[str]]] = {}
    for nt, bodies in grammar.productions.items():
        if nt != grammar.start_symbol and nt not in productive:
            continue
        kept: List[List[str]] = []
        for body in bodies:
            if all(
                sym == EPSILON
                or sym in grammar.terminals
                or sym in productive
                for sym in body
            ):
                kept.append(list(body))
        if kept or nt == grammar.start_symbol:
            productions[nt] = _dedupe(kept)

    # Step 2: drop unreachable non-terminals.
    reachable: Set[str] = set()
    stack = [grammar.start_symbol]
    while stack:
        nt = stack.pop()
        if nt in reachable:
            continue
        reachable.add(nt)
        for body in productions.get(nt, []):
            for sym in body:
                if sym in productions and sym not in reachable:
                    stack.append(sym)

    productions = {nt: bodies for nt, bodies in productions.items() if nt in reachable}

    logger.info("Removed useless symbols (%d non-terminals remain)", len(productions))
    return Grammar(start_symbol=grammar.start_symbol, productions=productions)


def remove_epsilon_productions(grammar: Grammar) -> Grammar:
    """Remove ``A -> ε`` productions while preserving the language.

    If the start symbol is nullable, a fresh start symbol ``S0 -> S | ε`` is
    introduced so the empty string is still generated.

    Args:
        grammar: The grammar to transform.

    Returns:
        A new :class:`Grammar`.
    """
    if not has_epsilon_productions(grammar):
        return grammar

    nullable = _nullable(grammar)
    start = grammar.start_symbol
    start_is_nullable = start in nullable
    fresh = _fresh_name_factory(grammar)

    productions: Dict[str, List[List[str]]] = {}
    if start_is_nullable:
        new_start = fresh(start)
        productions[new_start] = [[start], []]
        new_start_symbol = new_start
    else:
        new_start_symbol = start

    for nt, bodies in grammar.productions.items():
        out: List[List[str]] = []
        for body in bodies:
            if not body:
                # Explicit ε: dropped entirely. If the start symbol is
                # nullable the fresh start symbol reproduces ε instead.
                continue

            nullable_positions = [
                i for i, sym in enumerate(body) if sym in nullable
            ]
            for size in range(len(nullable_positions) + 1):
                for combo in itertools.combinations(nullable_positions, size):
                    removed = set(combo)
                    new_body = [
                        sym for i, sym in enumerate(body) if i not in removed
                    ]
                    if not new_body:
                        # Would produce A -> ε, which we are removing. If the
                        # start symbol was nullable, the fresh start symbol
                        # reproduces ε instead.
                        continue
                    out.append(new_body)
        productions[nt] = _dedupe(out)

    logger.info(
        "Removed ε-productions (nullable: %s)", sorted(nullable)
    )
    return Grammar(start_symbol=new_start_symbol, productions=productions)


def remove_unit_productions(grammar: Grammar) -> Grammar:
    """Remove unit productions ``A -> B`` (single non-terminal body).

    Args:
        grammar: The grammar to transform.

    Returns:
        A new :class:`Grammar`.
    """
    if not has_unit_productions(grammar):
        return grammar

    # Unit-reachability closure: which non-terminals each one reduces to via
    # one or more unit productions.
    closure: Dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            if len(body) == 1 and body[0] in grammar.non_terminals:
                closure[nt].add(body[0])

    changed = True
    while changed:
        changed = False
        for nt in grammar.non_terminals:
            expanded = set(closure[nt])
            for other in closure[nt]:
                expanded |= closure.get(other, set())
            if expanded != closure[nt]:
                closure[nt] = expanded
                changed = True

    productions: Dict[str, List[List[str]]] = {}
    for nt in grammar.non_terminals:
        out: List[List[str]] = []
        for source in {nt} | closure[nt]:
            for body in grammar.productions.get(source, []):
                is_unit = len(body) == 1 and body[0] in grammar.non_terminals
                if is_unit:
                    continue
                out.append(list(body))
        productions[nt] = _dedupe(out)

    logger.info("Removed unit productions")
    return Grammar(start_symbol=grammar.start_symbol, productions=productions)


def normalize_grammar(
    grammar: Grammar,
    remove_epsilon: bool = False,
    remove_unit: bool = False,
    remove_useless: bool = False,
) -> Grammar:
    """Apply the requested normalisations in a fixed order.

    Order: useless symbols, then ε-productions, then unit productions.

    Args:
        grammar: The source grammar.
        remove_epsilon: Eliminate ε-productions.
        remove_unit: Eliminate unit productions.
        remove_useless: Eliminate unreachable/non-generating symbols.

    Returns:
        The normalised grammar (or the original object when nothing requested).
    """
    result = grammar
    if remove_useless:
        result = remove_useless_symbols(result)
    if remove_epsilon:
        result = remove_epsilon_productions(result)
    if remove_unit:
        result = remove_unit_productions(result)
    return result