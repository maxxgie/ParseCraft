"""Parse tree data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParseTreeNode:
    """Represents a node in a parse tree.

    Attributes:
        symbol: The grammar symbol (terminal or non-terminal).
        value: The actual input value for terminals.
        children: List of child nodes.
        parent: Reference to the parent node.
    """

    symbol: str
    value: str = ""
    children: List["ParseTreeNode"] = field(default_factory=list)
    parent: Optional["ParseTreeNode"] = None

    def add_child(self, child: "ParseTreeNode") -> None:
        """Add a child node to this node.

        Args:
            child: The child node to add.
        """
        child.parent = self
        self.children.append(child)

    def is_leaf(self) -> bool:
        """Check if this node is a leaf (no children).

        Returns:
            True if the node has no children.
        """
        return len(self.children) == 0

    def to_string(self, indent: int = 0) -> str:
        """Return a string representation of the parse tree.

        Args:
            indent: Current indentation level.

        Returns:
            Multi-line string representation.
        """
        prefix = "  " * indent
        value_str = self.value if self.value else self.symbol
        result = f"{prefix}{self.symbol} ({value_str})\n"
        for child in self.children:
            result += child.to_string(indent + 1)
        return result

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"ParseTreeNode(symbol={self.symbol!r}, value={self.value!r})"