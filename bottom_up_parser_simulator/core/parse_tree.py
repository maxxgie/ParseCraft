"""Parse-tree construction and rendering helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.parse_tree import ParseTreeNode


def make_leaf(terminal: str, value: Optional[str] = None) -> ParseTreeNode:
    """Create a leaf node for a terminal.

    Args:
        terminal: The terminal symbol (used as the node label).
        value: The matched input value; defaults to ``terminal``.

    Returns:
        A leaf :class:`ParseTreeNode`.
    """
    return ParseTreeNode(symbol=terminal, value=value if value is not None else terminal)


def make_internal(lhs: str, children: List[ParseTreeNode]) -> ParseTreeNode:
    """Create an internal node for a reduction ``lhs -> children``.

    Args:
        lhs: The non-terminal on the left-hand side of the production.
        children: The already-built child nodes, left to right.

    Returns:
        A :class:`ParseTreeNode` with the given children attached.
    """
    node = ParseTreeNode(symbol=lhs)
    for child in children:
        node.add_child(child)
    return node


def tree_to_string(root: Optional[ParseTreeNode]) -> str:
    """Render a parse tree as an indented, human-readable string.

    Args:
        root: The root of the parse tree (or ``None``).

    Returns:
        A multi-line string, or a placeholder if ``root`` is ``None``.
    """
    if root is None:
        return "(no parse tree)"
    return root.to_string().rstrip("\n")


def tree_to_dict(root: Optional[ParseTreeNode]) -> Optional[Dict[str, Any]]:
    """Convert a parse tree into a nested dictionary (useful for GUI trees).

    Each node is represented as::

        {"symbol": str, "value": str, "children": [...]}

    Args:
        root: The root of the parse tree (or ``None``).

    Returns:
        The nested dictionary, or ``None`` if ``root`` is ``None``.
    """
    if root is None:
        return None

    def convert(node: ParseTreeNode) -> Dict[str, Any]:
        return {
            "symbol": node.symbol,
            "value": node.value,
            "children": [convert(child) for child in node.children],
        }

    return convert(root)


def tree_depth(root: Optional[ParseTreeNode]) -> int:
    """Return the depth of the parse tree (root has depth 1)."""
    if root is None:
        return 0
    if not root.children:
        return 1
    return 1 + max(tree_depth(child) for child in root.children)


def count_nodes(root: Optional[ParseTreeNode]) -> int:
    """Return the total number of nodes in the parse tree."""
    if root is None:
        return 0
    return 1 + sum(count_nodes(child) for child in root.children)


def collapse_unary_chains(root: Optional[ParseTreeNode]) -> Optional[ParseTreeNode]:
    """Return a copy of the tree with single-child (grammar-only) nodes removed.

    Unit productions and ``E -> T -> F`` style chains are collapsed, and
    ε-production nodes are dropped, while operators and operands are preserved.

    Args:
        root: The parse-tree root.

    Returns:
        A new, simplified :class:`ParseTreeNode` (or ``None``).
    """
    if root is None:
        return None

    # Drop ε-production nodes (a non-terminal whose only child is ε).
    if (
        len(root.children) == 1
        and root.children[0].symbol == "ε"
        and not root.children[0].children
    ):
        return None

    new_children = []
    for child in root.children:
        collapsed = collapse_unary_chains(child)
        if collapsed is not None:
            new_children.append(collapsed)

    if not new_children:
        # A genuine terminal leaf is kept; a node whose children all vanished
        # (an all-ε production) is dropped.
        if root.children:
            return None
        return ParseTreeNode(symbol=root.symbol, value=root.value)

    if len(new_children) == 1:
        return new_children[0]

    new_node = ParseTreeNode(symbol=root.symbol, value=root.value)
    for child in new_children:
        new_node.add_child(child)
    return new_node