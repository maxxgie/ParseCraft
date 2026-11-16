"""Grammar transformations: left-recursion removal and left factoring.

These are classic grammar-normalisation passes that are usually applied
*before* constructing an LL/LR automaton:

* :func:`eliminate_left_recursion` removes immediate and indirect left
  recursion (``A -> A α | β`` becomes ``A -> β A'``, ``A' -> α A' | ε``).
* :func:`left_factor` extracts common prefixes so that a predictive parser has
  a single choice for each input (``A -> α β1 | α β2`` becomes
  ``A -> α A'``, ``A' -> β1 | β2``).

Both functions are pure: they take a :class:`~models.grammar.Grammar` and
return a new one, leaving the input untouched.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)

# The automaton augments every grammar with this production, so user-level
# transformations must never emit a non-terminal with this name.
AUGMENTED_START = "S'"


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def _dedupe(bodies: List[List[str]]) -> List[List[str]]:
    """Return ``bodies`` without duplicates, preserving order."""
    seen: Set[Tuple[str, ...]] = set()
    result: List[List[str]] = []
    for body in bodies:
        key = tuple(body)
        if key in seen:
            continue
        seen.add(key)
        result.append(list(body))
    return result


def _longest_common_prefix(sequences: List[Tuple[str, ...]]) -> List[str]:
    """Return the longest common prefix shared by all sequences."""
    if not sequences:
        return []
    prefix = list(sequences[0])
    for seq in sequences[1:]:
        i = 0
        while i < len(prefix) and i < len(seq) and prefix[i] == seq[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


def _compute_nullable(grammar: Grammar) -> Set[str]:
    """Return the set of non-terminals that can derive the empty string."""
    nullable: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nt, bodies in grammar.productions.items():
            if nt in nullable:
                continue
            for body in bodies:
                if all(
                    sym in nullable or grammar.is_epsilon(sym) for sym in body
                ):
                    nullable.add(nt)
                    changed = True
                    break
    return nullable


def _make_fresh_name_factory(
    grammar: Grammar, productions: Dict[str, List[List[str]]]
):
    """Return a ``fresh(base)`` callable producing unused non-terminal names."""

    used: Set[str] = set(grammar.non_terminals) | set(grammar.terminals)

    def fresh(base: str) -> str:
        name = base + "'"
        while name in used or name in productions or name == AUGMENTED_START:
            name += "'"
        used.add(name)
        return name

    return fresh


# ----------------------------------------------------------------------
# Availability checks
# ----------------------------------------------------------------------
def has_left_recursion(grammar: Grammar) -> bool:
    """Return ``True`` if the grammar has immediate or indirect left recursion."""
    # Immediate left recursion: A -> A ...
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            if body and body[0] == nt:
                return True

    # Indirect left recursion via the left-corner graph.
    nullable = _compute_nullable(grammar)
    graph: Dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            for sym in body:
                if sym in grammar.non_terminals:
                    graph[nt].add(sym)
                    if sym not in nullable:
                        break
                else:
                    break

    for start in grammar.non_terminals:
        visited: Set[str] = set()
        stack = list(graph[start])
        while stack:
            node = stack.pop()
            if node == start:
                return True
            if node not in visited:
                visited.add(node)
                stack.extend(graph[node])
    return False


def has_common_prefixes(grammar: Grammar) -> bool:
    """Return ``True`` if any non-terminal has two productions sharing a prefix."""
    for bodies in grammar.productions.values():
        counts: Dict[str, int] = {}
        for body in bodies:
            if body:
                counts[body[0]] = counts.get(body[0], 0) + 1
        if any(count > 1 for count in counts.values()):
            return True
    return False


# ----------------------------------------------------------------------
# Left-recursion removal
# ----------------------------------------------------------------------
def _eliminate_immediate(
    productions: Dict[str, List[List[str]]], non_terminal: str, fresh
) -> None:
    """Remove immediate left recursion from a single non-terminal."""
    bodies = productions.get(non_terminal, [])
    alpha: List[List[str]] = []  # A -> A α
    beta: List[List[str]] = []  # A -> β (does not start with A)
    for body in bodies:
        if body and body[0] == non_terminal:
            alpha.append(body[1:])
        else:
            beta.append(body)

    if not alpha:
        return

    new_nt = fresh(non_terminal)

    if beta:
        productions[non_terminal] = _dedupe([b + [new_nt] for b in beta])
    else:
        # Only left-recursive; the grammar still derives via the new NT.
        productions[non_terminal] = [[new_nt]]

    tail_bodies: List[List[str]] = [a + [new_nt] for a in alpha]
    tail_bodies.append([])  # A' -> ε
    productions[new_nt] = _dedupe(tail_bodies)


def eliminate_left_recursion(grammar: Grammar) -> Grammar:
    """Return a new grammar with all left recursion removed.

    Implements the standard ordered algorithm that also handles *indirect*
    left recursion by repeatedly substituting earlier non-terminals and then
    eliminating immediate left recursion.

    Args:
        grammar: The grammar to transform.

    Returns:
        A new :class:`Grammar`; the input is not modified.
    """
    order: List[str] = list(grammar.productions.keys())
    productions: Dict[str, List[List[str]]] = {
        nt: [list(body) for body in grammar.productions[nt]] for nt in order
    }
    fresh = _make_fresh_name_factory(grammar, productions)

    for i, current in enumerate(order):
        # Substitute indirect recursion: current -> earlier γ
        for j in range(i):
            earlier = order[j]
            rewritten: List[List[str]] = []
            for body in productions[current]:
                if body and body[0] == earlier:
                    for delta in productions[earlier]:
                        rewritten.append(list(delta) + body[1:])
                else:
                    rewritten.append(list(body))
            productions[current] = _dedupe(rewritten)

        _eliminate_immediate(productions, current, fresh)

    logger.info("Left recursion removed from grammar")
    return Grammar(start_symbol=grammar.start_symbol, productions=productions)


# ----------------------------------------------------------------------
# Left factoring
# ----------------------------------------------------------------------
def left_factor(grammar: Grammar) -> Grammar:
    """Return a new grammar with common prefixes factored out.

    Args:
        grammar: The grammar to transform.

    Returns:
        A new :class:`Grammar`; the input is not modified.
    """
    new_productions: Dict[str, List[List[str]]] = {}
    fresh = _make_fresh_name_factory(grammar, new_productions)

    def factor_into(lhs: str, bodies: List[List[str]]) -> None:
        groups: Dict[str, List[List[str]]] = {}
        epsilon: List[List[str]] = []
        for body in _dedupe(bodies):
            if not body:
                epsilon.append([])
            else:
                groups.setdefault(body[0], []).append(body)

        result: List[List[str]] = []
        for sym, group in groups.items():
            if len(group) == 1:
                result.append(list(group[0]))
                continue
            tails = [tuple(body[1:]) for body in group]
            common = _longest_common_prefix(tails)
            sub = fresh(lhs)
            remainders = [list(tail[len(common):]) for tail in tails]
            result.append([sym] + common + [sub])
            factor_into(sub, remainders)

        result.extend(epsilon)
        new_productions[lhs] = _dedupe(result)

    for lhs, bodies in grammar.productions.items():
        factor_into(lhs, [list(body) for body in bodies])

    logger.info("Left factoring applied to grammar")
    return Grammar(start_symbol=grammar.start_symbol, productions=new_productions)


# ----------------------------------------------------------------------
# Convenience
# ----------------------------------------------------------------------
def apply_transforms(
    grammar: Grammar,
    remove_left_recursion: bool = False,
    left_factoring: bool = False,
) -> Grammar:
    """Apply the requested transformations in a fixed order.

    Left-recursion removal runs before left factoring.

    Args:
        grammar: The source grammar.
        remove_left_recursion: Whether to eliminate left recursion.
        left_factoring: Whether to factor common prefixes.

    Returns:
        The transformed grammar (or the original object when no transform is
        requested).
    """
    result = grammar
    if remove_left_recursion:
        result = eliminate_left_recursion(result)
    if left_factoring:
        result = left_factor(result)
    return result


def describe_features(grammar: Grammar) -> str:
    """Return a short human-readable note about the grammar's shape."""
    notes: List[str] = []
    if has_left_recursion(grammar):
        notes.append("left recursion detected")
    if has_common_prefixes(grammar):
        notes.append("common prefixes detected")
    return ", ".join(notes) if notes else "no left recursion or common prefixes"