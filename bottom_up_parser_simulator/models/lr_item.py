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

    def to_string(self, lhs_width: int | None = None) -> str:
        """Return a textbook-style representation of the item.

        The dot is rendered as ``•`` (U+2022) and is placed so that the
        productions of a state line up in a monospace font. When ``lhs_width``
        is given, the left-hand side is padded to that width, which keeps the
        dots aligned across items with different non-terminal names.

        Args:
            lhs_width: Optional width to pad the left-hand side to.

        Returns:
            String like ``[A -> α • β , a]`` for LR(1) or ``A -> α • β`` for
            LR(0).
        """
        lhs = self.lhs if lhs_width is None else self.lhs.ljust(lhs_width)
        before = list(self.rhs[: self.dot])
        after = list(self.rhs[self.dot :])
        if not before:
            body = "•" + " ".join(after)
        elif not after:
            body = " ".join(before) + "•"
        else:
            body = " ".join(before) + "• " + " ".join(after)
        if self.lookahead:
            return f"[{lhs} -> {body} , {self.lookahead}]"
        return f"{lhs} -> {body}"

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