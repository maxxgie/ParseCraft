"""Parse-tree construction and rendering helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

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


# ---------------------------------------------------------------------------
# Display helpers (preserve original node references so callers can map a
# clicked/selected display row back to the real parse-tree node for inspection).
# ---------------------------------------------------------------------------
DisplayTree = List[Tuple[ParseTreeNode, List["DisplayTree"]]]


def build_display_tree(
    root: Optional[ParseTreeNode],
    collapse: bool = False,
    folded: Optional[Any] = None,
) -> Optional[Tuple[ParseTreeNode, List["DisplayTree"]]]:
    """Build a display tree that keeps references to the original nodes.

    Each entry is ``(original_node, [child_entries])``.  Unlike
    :func:`collapse_unary_chains` (which copies nodes and therefore loses the
    link back to the source tree), this preserves the original
    :class:`ParseTreeNode` instances so a UI can map a selection to the real
    node for inspection.

    Args:
        root: The parse-tree root.
        collapse: When ``True``, collapse single-child (grammar-only) nodes and
            drop ε-production branches, mirroring :func:`collapse_unary_chains`.
        folded: Optional set of ``id(node)`` whose children should be hidden
            (manual folding).  The node itself is still shown.

    Returns:
        ``(node, children)`` or ``None`` when the branch is hidden.
    """
    folded = folded or set()

    def build(node: ParseTreeNode):
        # Manual fold: show the node but not its children.
        if id(node) in folded:
            return (node, [])

        # Drop ε-production nodes (non-terminal whose only child is a leaf ε).
        if (
            collapse
            and len(node.children) == 1
            and node.children[0].is_leaf()
            and node.children[0].symbol == "ε"
        ):
            return None

        child_entries = []
        for child in node.children:
            entry = build(child)
            if entry is not None:
                child_entries.append(entry)

        if not child_entries:
            # A terminal leaf is kept; a node whose children all vanished
            # (an all-ε production) is dropped.
            if node.children:
                return None
            return (node, [])

        if collapse and len(child_entries) == 1 and not node.is_leaf():
            return child_entries[0]

        return (node, child_entries)

    return build(root)


def preorder(
    entry: Optional[Tuple[ParseTreeNode, List["DisplayTree"]]]
) -> List[ParseTreeNode]:
    """Return the original nodes of a display tree in preorder."""
    result: List[ParseTreeNode] = []
    if entry is None:
        return result
    node, children = entry
    result.append(node)
    for child in children:
        result.extend(preorder(child))
    return result


def subtree_ids(node: Optional[ParseTreeNode]) -> set:
    """Return ``{id(n)}`` for ``node`` and every descendant (original tree)."""
    if node is None:
        return set()
    ids = {id(node)}
    for child in node.children:
        ids |= subtree_ids(child)
    return ids