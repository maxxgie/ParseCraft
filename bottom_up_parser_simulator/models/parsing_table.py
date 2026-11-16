"""Parsing table data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TableAction:
    """Represents an action in the ACTION table.

    Attributes:
        action_type: Type of action - 'shift', 'reduce', 'accept', 'error'.
        state: Target state for shift actions.
        production_lhs: Left-hand side for reduce actions.
        production_rhs: Right-hand side for reduce actions.
        rule_number: 1-based production number for reduce actions.
    """

    action_type: str
    state: int | None = None
    production_lhs: str | None = None
    production_rhs: tuple[str, ...] | None = None
    rule_number: int | None = None

    def to_string(self) -> str:
        """Return a string representation of the action.

        Returns:
            String like 'S5', 'R2', 'ACC', or '.' for error.
        """
        if self.action_type == "shift":
            return f"S{self.state}"
        elif self.action_type == "reduce":
            return f"R{self.rule_number if self.rule_number is not None else self.state}"
        elif self.action_type == "accept":
            return "ACC"
        else:
            return "."

    def __str__(self) -> str:
        return self.to_string()


@dataclass
class Conflict:
    """A detected ACTION-table conflict.

    Attributes:
        state: The parser state in which the conflict occurs.
        terminal: The terminal (lookahead) on which the conflict occurs.
        actions: The competing actions (>= 2) for this cell.
    """

    state: int
    terminal: str
    actions: List[TableAction] = field(default_factory=list)

    @property
    def has_shift(self) -> bool:
        """Whether any competing action is a shift."""
        return any(a.action_type == "shift" for a in self.actions)

    @property
    def has_reduce(self) -> bool:
        """Whether any competing action is a reduce."""
        return any(a.action_type == "reduce" for a in self.actions)

    @property
    def has_accept(self) -> bool:
        """Whether any competing action is an accept."""
        return any(a.action_type == "accept" for a in self.actions)

    @property
    def conflict_type(self) -> str:
        """Return ``shift-reduce``, ``reduce-reduce``, ``accept`` or ``other``."""
        if self.has_accept:
            return "accept"
        if self.has_shift and self.has_reduce:
            return "shift-reduce"
        if self.has_reduce:
            return "reduce-reduce"
        return "other"

    def actions_summary(self) -> str:
        """Return a compact description of the competing actions."""
        return " / ".join(a.to_string() for a in self.actions)

    @property
    def message(self) -> str:
        """Return a human-readable conflict description."""
        return (
            f"State {self.state}, '{self.terminal}': {self.conflict_type} conflict "
            f"({self.actions_summary()})"
        )

    def __str__(self) -> str:
        return self.message


@dataclass
class ParseTable:
    """Represents an LR parsing table.

    Attributes:
        action: Dictionary mapping (state, terminal) to TableAction.
        goto: Dictionary mapping (state, non_terminal) to target state.
        num_states: Number of states in the table.
        terminals: List of terminal symbols.
        non_terminals: List of non-terminal symbols.
    """

    action: Dict[Tuple[int, str], TableAction] = field(default_factory=dict)
    goto: Dict[Tuple[int, str], int] = field(default_factory=dict)
    num_states: int = 0
    terminals: List[str] = field(default_factory=list)
    non_terminals: List[str] = field(default_factory=list)

    def get_action(self, state: int, terminal: str) -> TableAction | None:
        """Get the action for a state and terminal.

        Args:
            state: The parser state.
            terminal: The input terminal.

        Returns:
            The TableAction, or None if no action is defined.
        """
        return self.action.get((state, terminal))

    def get_goto(self, state: int, non_terminal: str) -> int | None:
        """Get the target state for a non-terminal transition.

        Args:
            state: The parser state.
            non_terminal: The non-terminal symbol.

        Returns:
            The target state ID, or None if no transition exists.
        """
        return self.goto.get((state, non_terminal))

    def to_action_string(self) -> str:
        """Return a string representation of the ACTION table.

        Returns:
            Multi-line string with the ACTION table.
        """
        if not self.terminals:
            return "Empty ACTION table"

        header = "State\t" + "\t".join(self.terminals)
        lines = [header]

        for state in range(self.num_states):
            row = [str(state)]
            for terminal in self.terminals:
                action = self.get_action(state, terminal)
                row.append(action.to_string() if action else ".")
            lines.append("\t".join(row))

        return "\n".join(lines)

    def to_goto_string(self) -> str:
        """Return a string representation of the GOTO table.

        Returns:
            Multi-line string with the GOTO table.
        """
        if not self.non_terminals:
            return "Empty GOTO table"

        header = "State\t" + "\t".join(self.non_terminals)
        lines = [header]

        for state in range(self.num_states):
            row = [str(state)]
            for non_terminal in self.non_terminals:
                target = self.get_goto(state, non_terminal)
                row.append(str(target) if target is not None else ".")
            lines.append("\t".join(row))

        return "\n".join(lines)