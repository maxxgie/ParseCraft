"""LR automaton construction."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.grammar import Grammar
from models.lr_item import LRItem

from core.closure import closure, closure_with_trace
from core.goto import goto, goto_with_trace
from core.grammar_engine import ordered_symbols, production_order_map
from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationIssue:
    """A single state-validation finding.

    Attributes:
        state: The state the finding belongs to (``None`` for global checks).
        check: The name of the check (e.g. ``Closure complete``).
        ok: ``True`` when the check passed.
        detail: Additional explanation for failures.
    """

    state: int | None
    check: str
    ok: bool
    detail: str = ""


@dataclass
class LRState:
    """Represents a state in the LR automaton.

    Attributes:
        state_id: Unique identifier for the state.
        items: Set of LR items in this state.
        transitions: Dictionary mapping symbols to target state IDs.
        production_order: Mapping from ``(lhs, rhs)`` to its production index,
            used to display items in grammar (definition) order rather than
            alphabetically.
    """

    state_id: int
    items: set[LRItem] = field(default_factory=set)
    transitions: dict[str, int] = field(default_factory=dict)
    production_order: dict[tuple[str, tuple[str, ...]], int] = field(
        default_factory=dict
    )

    def sorted_items(self) -> list[LRItem]:
        """Return the items in textbook order (production order, then dot).

        Items are grouped by the production that generated them, in the order
        the productions appear in the grammar. The closure algorithm may add
        items, but never reorders them; this method only imposes the display
        order.

        Returns:
            The state's items as a list in display order.
        """
        if self.production_order:
            return sorted(
                self.items,
                key=lambda item: (
                    self.production_order.get((item.lhs, item.rhs), 1 << 30),
                    item.dot,
                    item.lookahead,
                ),
            )
        return sorted(
            self.items, key=lambda item: (item.lhs, item.rhs, item.dot, item.lookahead)
        )

    def get_items_string(self) -> str:
        """Return the items as an aligned, multi-line string.

        Returns:
            Multi-line string of items with aligned dots.
        """
        items = self.sorted_items()
        width = max((len(item.lhs) for item in items), default=0)
        return "\n".join(item.to_string(lhs_width=width) for item in items)

    def get_transition_rows(self) -> list[tuple[int, str, str, int | None]]:
        """Return one row per item that consumes a symbol.

        Each row is ``(state_id, configuration, consume, next_state)``. Items
        whose dot is at the end (completed items) consume nothing and are
        omitted. The consume symbol is shown beside the item that generated the
        transition, exactly as in handwritten lecture notes.

        Returns:
            A list of ``(state, configuration, symbol, target)`` tuples.
        """
        items = self.sorted_items()
        width = max((len(item.lhs) for item in items), default=0)
        rows: list[tuple[int, str, str, int | None]] = []
        for item in items:
            symbol = item.next_symbol()
            if symbol is None:
                continue
            target = self.transitions.get(symbol)
            rows.append(
                (self.state_id, item.to_string(lhs_width=width), symbol, target)
            )
        return rows

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

    def __init__(
        self, grammar: Grammar, augmented_grammar: Grammar | None = None
    ) -> None:
        """Initialize the automaton.

        Args:
            grammar: The original grammar.
            augmented_grammar: The augmented grammar (with S' -> S).
        """
        self.grammar = grammar
        self.augmented_grammar = augmented_grammar or self._augment_grammar(grammar)
        self.states: list[LRState] = []
        self.transitions: dict[tuple[int, str], int] = {}
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
            rhs=tuple(
                self.augmented_grammar.get_productions_for(
                    self.augmented_grammar.start_symbol
                )[0]
            ),
            dot=0,
        )
        initial_items = closure({start_item}, self.augmented_grammar)
        initial_state = LRState(state_id=0, items=initial_items)
        self.states.append(initial_state)

        # Process states
        unprocessed = [0]
        state_ids = {frozenset(item.key() for item in initial_items): 0}
        # Symbols are visited in the order they appear in the grammar so that
        # state numbering matches textbook presentations (E, T, (, id, ...).
        symbol_order = ordered_symbols(self.augmented_grammar)

        while unprocessed:
            current_id = unprocessed.pop(0)
            current_state = self.states[current_id]

            # Collect all symbols that can be transitioned on
            symbols = set()
            for item in current_state.items:
                next_sym = item.next_symbol()
                if next_sym is not None:
                    symbols.add(next_sym)

            # Compute GOTO for each symbol, in grammar order.
            for symbol in symbol_order:
                if symbol not in symbols:
                    continue
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

        # Share the production ordering with every state for display.
        order = production_order_map(self.augmented_grammar)
        for state in self.states:
            state.production_order = order

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

    def get_transitions_from(self, state_id: int) -> dict[str, int]:
        """Get all transitions from a state.

        Args:
            state_id: The state ID.

        Returns:
            Dictionary mapping symbols to target state IDs.
        """
        return self.states[state_id].transitions

    def get_all_symbols(self) -> set[str]:
        """Get all symbols that appear in transitions.

        Returns:
            Set of all transition symbols.
        """
        symbols = set()
        for (_, symbol), _ in self.transitions.items():
            symbols.add(symbol)
        return symbols

    def kernel_items(self, state: LRState) -> set[LRItem]:
        """Return the kernel (seed) items of a state.

        The kernel is the set of items whose dot is not at the beginning,
        plus the augmented start item for the initial state. Taking the
        closure of the kernel reproduces the whole state, which is exactly
        what the Closure Steps view displays.

        Args:
            state: The state to inspect.

        Returns:
            The kernel item set.
        """
        aug_start = self.augmented_grammar.start_symbol
        return {
            item
            for item in state.items
            if item.dot > 0 or (item.lhs == aug_start and item.dot == 0)
        }

    def closure_trace(self, state_id: int) -> dict[str, object]:
        """Recompute a state's closure and return a step-by-step trace.

        Args:
            state_id: The state to recompute.

        Returns:
            A dict with ``state``, ``kernel``, ``result``, ``steps`` and
            ``matches`` (whether the recomputed closure equals the stored
            state).
        """
        state = self.get_state(state_id)
        kernel = self.kernel_items(state)
        result, steps = closure_with_trace(kernel, self.augmented_grammar)
        return {
            "state": state_id,
            "kernel": kernel,
            "result": result,
            "steps": steps,
            "matches": result == state.items,
        }

    def goto_trace(self, state_id: int, symbol: str) -> dict[str, object]:
        """Recompute a GOTO transition and return a step-by-step trace.

        Args:
            state_id: The source state.
            symbol: The grammar symbol to advance over.

        Returns:
            A dict with ``symbol``, ``moved``, ``closure_steps`` and ``target``
            (the stored target state id, if any).
        """
        state = self.get_state(state_id)
        result, trace = goto_with_trace(state.items, symbol, self.augmented_grammar)
        trace["target"] = self.transitions.get((state_id, symbol))
        trace["result"] = result
        return trace

    def to_dot(self) -> str:
        """Generate a Graphviz DOT representation of the automaton.

        Returns:
            DOT format string.
        """
        lines = ["digraph LRAutomaton {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box, style=filled, fillcolor=lightyellow];")

        for state in self.states:
            label = f"State {state.state_id}\\n"
            items_str = state.get_items_string().replace("\n", "\\n")
            label += items_str
            lines.append(f'  {state.state_id} [label="{label}"];')

        for (from_id, symbol), to_id in self.transitions.items():
            lines.append(f'  {from_id} -> {to_id} [label="{symbol}"];')

        lines.append("}")
        return "\n".join(lines)


def transition_rows(automaton) -> list[tuple[int, str, str, int | None]]:
    """Return the state-transition table rows for any LR automaton.

    Args:
        automaton: An object exposing ``states`` (each an :class:`LRState`).

    Returns:
        A list of ``(state, configuration, consume, next_state)`` tuples in
        state order, then item (production) order.
    """
    rows: list[tuple[int, str, str, int | None]] = []
    for state in automaton.states:
        rows.extend(state.get_transition_rows())
    return rows


def format_transition_table(automaton) -> str:
    """Render the state-transition table as aligned plain text.

    The columns are ``State``, ``Configuration State``, ``Consume`` and
    ``Next State``, matching the layout used in compiler-construction notes.

    Args:
        automaton: An object exposing ``states``.

    Returns:
        A multi-line, column-aligned string.
    """
    headers = ("State", "Configuration State", "Consume", "Next State")
    rows = transition_rows(automaton)
    data = [
        [str(state), config, consume, "" if target is None else str(target)]
        for state, config, consume, target in rows
    ]
    widths = [len(header) for header in headers]
    for row in data:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [render(list(headers))]
    lines.append("  ".join("-" * width for width in widths))
    for row in data:
        lines.append(render(row))
    return "\n".join(lines)


def validate_automaton(automaton) -> list[ValidationIssue]:
    """Validate a constructed LR automaton against the textbook invariants.

    Checks performed for every state:

    * state numbering is contiguous and starts at 0;
    * the item set has no duplicates;
    * the closure is complete (every production of a next-symbol non-terminal
      is present with the dot at the start);
    * every item's next symbol has a transition;
    * every transition target is a valid state;
    * transitions recorded globally match each state's local transition map.

    Args:
        automaton: Any object exposing ``states``, ``transitions`` and
            ``augmented_grammar``.

    Returns:
        A list of :class:`ValidationIssue`; empty means the automaton is valid.
    """
    issues: list[ValidationIssue] = []
    states = automaton.states
    transitions = automaton.transitions
    aug = getattr(automaton, "augmented_grammar", None)

    if not states:
        issues.append(
            ValidationIssue(None, "Initial state", False, "automaton has no states")
        )
        return issues

    # Global: numbering and initial state.
    for index, state in enumerate(states):
        if state.state_id != index:
            issues.append(
                ValidationIssue(
                    state.state_id,
                    "State numbering",
                    False,
                    f"expected id {index}",
                )
            )
    if states[0].state_id != 0:
        issues.append(
            ValidationIssue(
                None, "Initial state", False, "state 0 must be the initial state"
            )
        )

    # Per-state checks.
    for state in states:
        keys = {item.key() for item in state.items}

        if len(keys) != len(state.items):
            issues.append(
                ValidationIssue(
                    state.state_id,
                    "No duplicate items",
                    False,
                    "duplicate LR items found",
                )
            )
        else:
            issues.append(ValidationIssue(state.state_id, "No duplicate items", True))

        if aug is not None:
            missing: list[str] = []
            for item in state.items:
                next_sym = item.next_symbol()
                if next_sym is None or next_sym not in aug.non_terminals:
                    continue
                for body in aug.get_productions_for(next_sym):
                    expected = LRItem(
                        lhs=next_sym,
                        rhs=tuple(body),
                        dot=0,
                        lookahead=item.lookahead,
                    )
                    if expected.key() not in keys:
                        text = f"{next_sym} -> {' '.join(body) if body else 'ε'}"
                        if text not in missing:
                            missing.append(text)
            if missing:
                issues.append(
                    ValidationIssue(
                        state.state_id,
                        "Closure complete",
                        False,
                        "missing: " + ", ".join(missing),
                    )
                )
            else:
                issues.append(ValidationIssue(state.state_id, "Closure complete", True))

        missing_transitions = sorted(
            {
                item.next_symbol()
                for item in state.items
                if item.next_symbol() is not None
                and item.next_symbol() not in state.transitions
            }
        )
        if missing_transitions:
            issues.append(
                ValidationIssue(
                    state.state_id,
                    "Transitions complete",
                    False,
                    "missing on: " + ", ".join(missing_transitions),
                )
            )
        else:
            issues.append(ValidationIssue(state.state_id, "Transitions complete", True))

        bad_targets = sorted(
            {
                target
                for target in state.transitions.values()
                if target < 0 or target >= len(states)
            }
        )
        if bad_targets:
            issues.append(
                ValidationIssue(
                    state.state_id,
                    "Transition targets valid",
                    False,
                    "invalid targets: " + ", ".join(str(t) for t in bad_targets),
                )
            )
        else:
            issues.append(
                ValidationIssue(state.state_id, "Transition targets valid", True)
            )

    # Global: reverse consistency between transitions and state maps.
    for (from_id, symbol), to_id in transitions.items():
        if from_id < 0 or from_id >= len(states):
            issues.append(
                ValidationIssue(
                    None,
                    "Transitions consistent",
                    False,
                    f"transition from invalid state {from_id}",
                )
            )
            continue
        if to_id < 0 or to_id >= len(states):
            issues.append(
                ValidationIssue(
                    from_id,
                    "Transitions consistent",
                    False,
                    f"transition on '{symbol}' targets invalid state {to_id}",
                )
            )
            continue
        if states[from_id].transitions.get(symbol) != to_id:
            issues.append(
                ValidationIssue(
                    from_id,
                    "Transitions consistent",
                    False,
                    f"state map for '{symbol}' does not match global transition",
                )
            )

    return issues
