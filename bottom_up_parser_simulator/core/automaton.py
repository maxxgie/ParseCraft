"""LR automaton construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

from core.logging_config import get_logger
from core.closure import closure
from core.goto import goto
from models.lr_item import LRItem
from models.grammar import Grammar

logger = get_logger(__name__)


@dataclass
class LRState:
    """Represents a state in the LR automaton.

    Attributes:
        state_id: Unique identifier for the state.
        items: Set of LR items in this state.
        transitions: Dictionary mapping symbols to target state IDs.
    """

    state_id: int
    items: Set[LRItem] = field(default_factory=set)
    transitions: Dict[str, int] = field(default_factory=dict)

    def get_items_string(self) -> str:
        """Return a string representation of the items in this state.

        Returns:
            Multi-line string of items.
        """
        sorted_items = sorted(self.items, key=lambda x: (x.lhs, x.rhs, x.dot, x.lookahead))
        return "\n".join(item.to_string() for item in sorted_items)

    def __str__(self) -> str:
        return f"State {self.state_id}:\n{self.get_items_string()}"


class LRAutomaton:
    """LR automaton for parsing.

    Attributes:
        grammar: The augmented grammar.
        states: List of LR states.
        transitions: Dictionary mapping (state_id, symbol) to target state ID.
        start_state: The starting state ID.
    """

    def __init__(self, grammar: Grammar, augmented_grammar: Grammar | None = None) -> None:
        """Initialize the automaton.

        Args:
            grammar: The original grammar.
            augmented_grammar: The augmented grammar (with S' -> S).
        """
        self.grammar = grammar
        self.augmented_grammar = augmented_grammar or self._augment_grammar(grammar)
        self.states: List[LRState] = []
        self.transitions: Dict[Tuple[int, str], int] = {}
        self.start_state: int = 0
        self._build_automaton()

    def _augment_grammar(self, grammar: Grammar) -> Grammar:
        """Augment the grammar by adding S' -> S.

        Args:
            grammar: The original grammar.

        Returns:
            Augmented grammar.
        """
        from core.grammar_engine import augment_grammar

        return augment_grammar(grammar)

    def _build_automaton(self) -> None:
        """Build the LR automaton states and transitions."""
        # Create initial state
        start_item = LRItem(
            lhs=self.augmented_grammar.start_symbol,
            rhs=tuple(self.augmented_grammar.get_productions_for(self.augmented_grammar.start_symbol)[0]),
            dot=0,
        )
        initial_items = closure({start_item}, self.augmented_grammar)
        initial_state = LRState(state_id=0, items=initial_items)
        self.states.append(initial_state)

        # Process states
        unprocessed = [0]
        state_ids = {frozenset(item.key() for item in initial_items): 0}

        while unprocessed:
            current_id = unprocessed.pop(0)
            current_state = self.states[current_id]

            # Collect all symbols that can be transitioned on
            symbols = set()
            for item in current_state.items:
                next_sym = item.next_symbol()
                if next_sym is not None:
                    symbols.add(next_sym)

            # Compute GOTO for each symbol
            for symbol in sorted(symbols):
                goto_items = goto(current_state.items, symbol, self.augmented_grammar)
                if not goto_items:
                    continue

                # Check if this item set already exists
                item_key = frozenset(item.key() for item in goto_items)
                if item_key in state_ids:
                    target_id = state_ids[item_key]
                else:
                    target_id = len(self.states)
                    state_ids[item_key] = target_id
                    new_state = LRState(state_id=target_id, items=goto_items)
                    self.states.append(new_state)
                    unprocessed.append(target_id)

                # Record transition
                self.transitions[(current_id, symbol)] = target_id
                current_state.transitions[symbol] = target_id

        logger.info("LR automaton built: %d states", len(self.states))

    def get_state(self, state_id: int) -> LRState:
        """Get a state by its ID.

        Args:
            state_id: The state ID.

        Returns:
            The LR state.

        Raises:
            IndexError: If state_id is out of range.
        """
        return self.states[state_id]

    def get_transitions_from(self, state_id: int) -> Dict[str, int]:
        """Get all transitions from a state.

        Args:
            state_id: The state ID.

        Returns:
            Dictionary mapping symbols to target state IDs.
        """
        return self.states[state_id].transitions

    def get_all_symbols(self) -> Set[str]:
        """Get all symbols that appear in transitions.

        Returns:
            Set of all transition symbols.
        """
        symbols = set()
        for (_, symbol), _ in self.transitions.items():
            symbols.add(symbol)
        return symbols

    def to_dot(self) -> str:
        """Generate a Graphviz DOT representation of the automaton.

        Returns:
            DOT format string.
        """
        lines = ["digraph LRAutomaton {"]
        lines.append("  rankdir=LR;")
        lines.append('  node [shape=box, style=filled, fillcolor=lightyellow];')

        for state in self.states:
            label = f"State {state.state_id}\\n"
            items_str = state.get_items_string().replace("\n", "\\n")
            label += items_str
            lines.append(f'  {state.state_id} [label="{label}"];')

        for (from_id, symbol), to_id in self.transitions.items():
            lines.append(f'  {from_id} -> {to_id} [label="{symbol}"];')

        lines.append("}")
        return "\n".join(lines)