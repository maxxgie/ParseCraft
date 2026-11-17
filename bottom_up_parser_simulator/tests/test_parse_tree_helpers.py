"""Tests for parse-tree helpers (collapse, rendering data)."""

from __future__ import annotations

from core.parse_tree import collapse_unary_chains, count_nodes
from core.topdown import analyze_topdown, simulate_topdown

LL1_GRAMMAR = """E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id"""


def _tree(text: str):
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, "LL(1)"), text)
    assert result.accepted, result.error
    return result.parse_tree


def test_collapse_reduces_nodes():
    tree = _tree("id")
    collapsed = collapse_unary_chains(tree)
    assert collapsed is not None
    assert count_nodes(collapsed) < count_nodes(tree)
    # E -> T -> F -> id collapses to the operand leaf.
    assert collapsed.symbol == "id"


def test_collapse_preserves_operators():
    tree = _tree("id+id")
    collapsed = collapse_unary_chains(tree)
    labels = []

    def walk(node):
        labels.append(node.symbol)
        for child in node.children:
            walk(child)

    walk(collapsed)
    assert "+" in labels


def test_collapse_none():
    assert collapse_unary_chains(None) is None