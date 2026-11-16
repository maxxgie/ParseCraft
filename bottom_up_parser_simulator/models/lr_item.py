"""LR item data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class LRItem:
    """Represents an LR(k) item.

    An LR item is a production with a dot position and optional lookahead
    for LR(1) items.

    Attributes:
        lhs: Left-hand side non-terminal.
        rhs: Right-hand side production body.
        dot: Position of the dot (0 to len(rhs)).
        lookahead: Lookahead symbol for LR(1) items. Empty string for LR(0).
    """

    lhs: str
    rhs: Tuple[str, ...]
    dot: int = 0
    lookahead: str = ""

    def __post_init__(self) -> None:
        """Validate the dot position."""
        if self.dot < 0 or self.dot > len(self.rhs):
            raise ValueError(
                f"Dot position {self.dot} out of range for production {self.lhs} -> {' '.join(self.rhs)}"
            )

    def next_symbol(self) -> str | None:
        """Return the symbol after the dot, or None if at end.

        Returns:
            The next symbol, or None if the item is a completed item.
        """
        if self.dot < len(self.rhs):
            return self.rhs[self.dot]
        return None

    def is_complete(self) -> bool:
        """Check if the item is a completed item (dot at end).

        Returns:
            True if the dot is at the end of the production.
        """
        return self.dot >= len(self.rhs)

    def advance_dot(self) -> "LRItem":
        """Return a new item with the dot advanced by one position.

        Returns:
            New LRItem with dot incremented by 1.

        Raises:
            ValueError: If the item is already complete.
        """
        if self.is_complete():
            raise ValueError("Cannot advance dot on a completed item")
        return LRItem(
            lhs=self.lhs,
            rhs=self.rhs,
            dot=self.dot + 1,
            lookahead=self.lookahead,
        )

    def with_lookahead(self, lookahead: str) -> "LRItem":
        """Return a new item with the given lookahead.

        Args:
            lookahead: The lookahead symbol.

        Returns:
            New LRItem with the specified lookahead.
        """
        return LRItem(
            lhs=self.lhs,
            rhs=self.rhs,
            dot=self.dot,
            lookahead=lookahead,
        )

    def to_string(self) -> str:
        """Return a string representation of the item.

        Returns:
            String like "[A -> α . β , a]" for LR(1) or "A -> α . β" for LR(0).
        """
        rhs_list = list(self.rhs)
        rhs_with_dot = rhs_list[: self.dot] + ["."] + rhs_list[self.dot :]
        body = " ".join(rhs_with_dot)
        if self.lookahead:
            return f"[{self.lhs} -> {body} , {self.lookahead}]"
        return f"{self.lhs} -> {body}"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"LRItem(lhs={self.lhs!r}, rhs={self.rhs!r}, dot={self.dot}, lookahead={self.lookahead!r})"

    def key(self) -> Tuple[str, Tuple[str, ...], int, str]:
        """Return a hashable key for the item.

        Returns:
            Tuple of (lhs, rhs, dot, lookahead).
        """
        return (self.lhs, self.rhs, self.dot, self.lookahead)