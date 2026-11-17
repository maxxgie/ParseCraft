"""Canonical LR(1) and LALR(1) automaton construction.

This module builds the LR(1) item-set collection (the "canonical" collection
used by CLR(1) parsers) and, optionally, the merged collection used by
LALR(1) parsers. Both share the :class:`LRState` structure defined in
:mod:`core.automaton`.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from core.automaton import LRState
from core.first_follow import compute_first
from core.grammar_engine import (
    augment_grammar as _augment_grammar,
    ordered_symbols,
    production_order_map,
)
from core.logging_config import get_logger
from models.grammar import Grammar
from models.lr_item import LRItem

logger = get_logger(__name__)

AUGMENTED_START = "S'"
END_MARKER = "$"
EPSILON = "ε"


def augment_grammar(grammar: Grammar) -> Grammar:
    """Return an augmented grammar with ``S' -> S``.

    Delegates to :func:`core.grammar_engine.augment_grammar` so that a grammar
    which already uses ``S'`` still gets a collision-free augmented start.

    Args:
        grammar: The original grammar.

    Returns:
        A new grammar whose start symbol produces the original start.
    """
    return _augment_grammar(grammar)


def _first_of_sequence(
    sequence: Tuple[str, ...], lookahead: str, first: Dict[str, Set[str]]
) -> Set[str]:
    """Compute FIRST(sequence · lookahead) for LR(1) closure.

    Args:
        sequence: The symbols following the non-terminal (the ``β`` part).
        lookahead: The current item's lookahead (the ``a`` part).
        first: Pre-computed FIRST sets.

    Returns:
        The set of terminal symbols that can begin ``sequence lookahead``.
    """
    result: Set[str] = set()
    all_derive_epsilon = True
    for sym in sequence:
        if sym == EPSILON:
            continue
        sym_first = first.get(sym, {sym})
        result |= sym_first - {EPSILON}
        if EPSILON not in sym_first:
            all_derive_epsilon = False
            break
    if all_derive_epsilon:
        result.add(lookahead)
    return result


def lr1_closure(
    items: Set[LRItem], grammar: Grammar, first: Dict[str, Set[str]]
) -> Set[LRItem]:
    """Compute the LR(1) closure of a set of items.

    For every item ``[A -> α . B β, a]`` and every production ``B -> γ``,
    adds ``[B -> . γ, b]`` for each ``b`` in ``FIRST(β a)``.

    Args:
        items: The seed set of LR(1) items.
        grammar: The (augmented) grammar.
        first: Pre-computed FIRST sets.

    Returns:
        The closure of ``items``.
    """
    result: Set[LRItem] = set(items)
    changed = True
    while changed:
        changed = False
        for item in list(result):
            next_sym = item.next_symbol()
            if next_sym is None or next_sym not in grammar.non_terminals:
                continue
            beta = item.rhs[item.dot + 1:]
            lookaheads = _first_of_sequence(beta, item.lookahead, first)
            for rhs in grammar.get_productions_for(next_sym):
                for la in lookaheads:
                    new_item = LRItem(
                        lhs=next_sym, rhs=tuple(rhs), dot=0, lookahead=la
                    )
                    if new_item not in result:
                        result.add(new_item)
                        changed = True
    logger.debug("LR(1) closure computed: %d items", len(result))
    return result


def lr1_goto(
    items: Set[LRItem], symbol: str, grammar: Grammar, first: Dict[str, Set[str]]
) -> Set[LRItem]:
    """Compute GOTO(items, symbol) for LR(1) items.

    Args:
        items: The current item set.
        symbol: The grammar symbol to advance over.
        grammar: The (augmented) grammar.
        first: Pre-computed FIRST sets.

    Returns:
        The closure of the advanced items.
    """
    moved: Set[LRItem] = set()
    for item in items:
        if item.next_symbol() == symbol:
            moved.add(item.advance_dot())
    if not moved:
        return set()
    return lr1_closure(moved, grammar, first)


class LR1Automaton:
    """LR(1) automaton (canonical collection).

    When ``merge`` is ``True`` the automaton is collapsed into an LALR(1)
    automaton by merging states that share the same LR(0) core.

    Attributes:
        grammar: The original grammar.
        augmented_grammar: The grammar augmented with ``S' -> S``.
        first: FIRST sets for the augmented grammar.
        states: List of :class:`LRState`.
        transitions: Mapping ``(state_id, symbol) -> target state id``.
        start_state: The start state id (always 0).
        merged: Whether this automaton was produced by LALR merging.
    """

    def __init__(self, grammar: Grammar, merge: bool = False) -> None:
        """Build the LR(1) (or LALR(1)) automaton.

        Args:
            grammar: The original grammar.
            merge: If ``True`` build the LALR(1) automaton, otherwise the
                canonical LR(1) automaton.
        """
        self.grammar = grammar
        self.augmented_grammar = augment_grammar(grammar)
        self.first = compute_first(self.augmented_grammar)
        self.states: List[LRState] = []
        self.transitions: Dict[Tuple[int, str], int] = {}
        self.start_state: int = 0
        self.merged = merge
        self._build()

        order = production_order_map(self.augmented_grammar)
        for state in self.states:
            state.production_order = order

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _start_items(self) -> Set[LRItem]:
        start = LRItem(
            lhs=self.augmented_grammar.start_symbol,
            rhs=(self.grammar.start_symbol,),
            dot=0,
            lookahead=END_MARKER,
        )
        return lr1_closure({start}, self.augmented_grammar, self.first)

    def _ordered_symbols(self, items: Set[LRItem]) -> List[str]:
        """Return the transition symbols of ``items`` in grammar order."""
        available = {
            item.next_symbol() for item in items if item.next_symbol() is not None
        }
        return [s for s in ordered_symbols(self.augmented_grammar) if s in available]

    def _build(self) -> None:
        initial = self._start_items()
        if self.merged:
            self._build_lalr(initial)
        else:
            self._build_canonical(initial)

    def _build_canonical(self, initial: Set[LRItem]) -> None:
        """Build the canonical LR(1) collection."""
        initial_state = LRState(state_id=0, items=initial)
        self.states.append(initial_state)
        unprocessed: List[int] = [0]
        state_ids: Dict[frozenset, int] = {
            frozenset(it.key() for it in initial): 0
        }

        while unprocessed:
            current_id = unprocessed.pop(0)
            current_state = self.states[current_id]
            for symbol in self._ordered_symbols(current_state.items):
                goto_items = lr1_goto(
                    current_state.items, symbol, self.augmented_grammar, self.first
                )
                if not goto_items:
                    continue
                key = frozenset(it.key() for it in goto_items)
                if key in state_ids:
                    target_id = state_ids[key]
                else:
                    target_id = len(self.states)
                    state_ids[key] = target_id
                    self.states.append(LRState(state_id=target_id, items=goto_items))
                    unprocessed.append(target_id)
                self.transitions[(current_id, symbol)] = target_id
                current_state.transitions[symbol] = target_id

        logger.info("Canonical LR(1) automaton built: %d states", len(self.states))

    def _build_lalr(self, initial: Set[LRItem]) -> None:
        """Build the LALR(1) collection by merging same-core LR(1) states."""
        # Step 1: build the canonical collection.
        canonical_states: List[Set[LRItem]] = [initial]
        canonical_ids: Dict[frozenset, int] = {
            frozenset(it.key() for it in initial): 0
        }
        canonical_edges: List[Tuple[int, str, int]] = []
        unprocessed: List[int] = [0]

        while unprocessed:
            current_id = unprocessed.pop(0)
            items = canonical_states[current_id]
            available = {
                it.next_symbol() for it in items if it.next_symbol() is not None
            }
            symbols = [
                s for s in ordered_symbols(self.augmented_grammar) if s in available
            ]
            for symbol in symbols:
                goto_items = lr1_goto(
                    items, symbol, self.augmented_grammar, self.first
                )
                if not goto_items:
                    continue
                key = frozenset(it.key() for it in goto_items)
                if key in canonical_ids:
                    target_id = canonical_ids[key]
                else:
                    target_id = len(canonical_states)
                    canonical_ids[key] = target_id
                    canonical_states.append(goto_items)
                    unprocessed.append(target_id)
                canonical_edges.append((current_id, symbol, target_id))

        # Step 2: merge states that share the same LR(0) core.
        core_to_merged: Dict[frozenset, int] = {}
        canonical_to_merged: List[int] = []
        merged_items: List[Set[LRItem]] = []
        for items in canonical_states:
            core = frozenset((it.lhs, it.rhs, it.dot) for it in items)
            if core not in core_to_merged:
                core_to_merged[core] = len(merged_items)
                merged_items.append(set())
            merged_id = core_to_merged[core]
            canonical_to_merged.append(merged_id)
            merged_items[merged_id].update(items)

        # Step 3: materialize merged states and transitions.
        for merged_id, items in enumerate(merged_items):
            self.states.append(LRState(state_id=merged_id, items=items))

        seen: Set[Tuple[int, str, int]] = set()
        for from_canon, symbol, to_canon in canonical_edges:
            from_merged = canonical_to_merged[from_canon]
            to_merged = canonical_to_merged[to_canon]
            edge = (from_merged, symbol, to_merged)
            if edge in seen:
                continue
            seen.add(edge)
            self.transitions[(from_merged, symbol)] = to_merged
            self.states[from_merged].transitions[symbol] = to_merged

        logger.info(
            "LALR(1) automaton built: %d states (merged from %d canonical states)",
            len(self.states),
            len(canonical_states),
        )

    # ------------------------------------------------------------------
    # Accessors (mirror LRAutomaton for a uniform interface)
    # ------------------------------------------------------------------
    def get_state(self, state_id: int) -> LRState:
        """Return the state with the given id."""
        return self.states[state_id]

    def get_transitions_from(self, state_id: int) -> Dict[str, int]:
        """Return the transitions out of ``state_id``."""
        return self.states[state_id].transitions

    def get_all_symbols(self) -> Set[str]:
        """Return every symbol used as a transition label."""
        symbols: Set[str] = set()
        for (_, symbol) in self.transitions:
            symbols.add(symbol)
        return symbols

    def to_dot(self) -> str:
        """Return a Graphviz DOT representation of the automaton."""
        lines = ["digraph LRAutomaton {", "  rankdir=LR;"]
        lines.append('  node [shape=box, style=filled, fillcolor=lightyellow];')
        for state in self.states:
            label = f"State {state.state_id}\\n"
            label += state.get_items_string().replace("\n", "\\n")
            lines.append(f'  {state.state_id} [label="{label}"];')
        for (from_id, symbol), to_id in self.transitions.items():
            lines.append(f'  {from_id} -> {to_id} [label="{symbol}"];')
        lines.append("}")
        return "\n".join(lines)