"""Abstract syntax tree construction from a parse tree.

Collapses grammar-only nodes (unit productions and single-child chains) and
drops ε nodes to produce a simplified tree that keeps operators and operands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.topdown.common import EPSILON
from models.parse_tree import ParseTreeNode


@dataclass
class AstNode:
    """A node in an abstract syntax tree.

    Attributes:
        label: The operator or construct label.
        value: The operand value (for leaves).
        children: Child nodes.
    """

    label: str
    value: str = ""
    children: List["AstNode"] = field(default_factory=list)

    def add_child(self, child: "AstNode") -> None:
        """Append ``child`` to this node."""
        self.children.append(child)

    def is_leaf(self) -> bool:
        """Return ``True`` when the node has no children."""
        return not self.children

    def to_string(self, indent: int = 0) -> str:
        """Render the AST as an indented string."""
        prefix = "  " * indent
        label = self.value if self.is_leaf() and self.value else self.label
        lines = [f"{prefix}{self.label}" + (f" ({label})" if label and label != self.label else "")]
        for child in self.children:
            lines.append(child.to_string(indent + 1))
        return "\n".join(lines)

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.to_string()


def _simplify(
    node: ParseTreeNode,
    collapse_unary: bool,
    lift_operators: bool,
) -> Optional[AstNode]:
    if not node.children:
        if node.symbol == EPSILON or (node.value == EPSILON and not node.symbol):
            return None
        return AstNode(label=node.symbol, value=node.value)

    first_is_terminal = (
        node.children[0].is_leaf() and node.children[0].symbol != EPSILON
    )

    simplified: List[AstNode] = []
    for child in node.children:
        if child.symbol == EPSILON and not child.children:
            continue
        child_ast = _simplify(child, collapse_unary, lift_operators)
        if child_ast is not None:
            simplified.append(child_ast)

    if not simplified:
        return None
    if collapse_unary and len(simplified) == 1:
        return simplified[0]
    if lift_operators and len(node.children) >= 2 and first_is_terminal:
        operator = simplified[0]
        return AstNode(
            label=operator.value or operator.label,
            children=simplified[1:],
        )
    return AstNode(label=node.symbol, children=simplified)


def parse_tree_to_ast(
    root: Optional[ParseTreeNode],
    collapse_unary: bool = True,
    lift_operators: bool = True,
) -> Optional[AstNode]:
    """Convert a parse tree into a simplified abstract syntax tree.

    Args:
        root: The parse-tree root.
        collapse_unary: Collapse single-child chains (e.g. ``E -> T -> F``).
        lift_operators: Promote a leading operator terminal to the node label
            (e.g. ``E' -> + T E'`` becomes ``+`` with children ``T`` and ``E'``).

    Returns:
        The AST root, or ``None`` when ``root`` is ``None`` or empty.
    """
    if root is None:
        return None
    return _simplify(root, collapse_unary, lift_operators)


def ast_to_dict(node: Optional[AstNode]) -> Optional[Dict[str, Any]]:
    """Convert an AST into a nested dictionary (for GUI tree widgets)."""
    if node is None:
        return None
    return {
        "label": node.label,
        "value": node.value,
        "children": [ast_to_dict(c) for c in node.children],
    }


def count_ast_nodes(node: Optional[AstNode]) -> int:
    """Return the total number of nodes in the AST."""
    if node is None:
        return 0
    return 1 + sum(count_ast_nodes(c) for c in node.children)