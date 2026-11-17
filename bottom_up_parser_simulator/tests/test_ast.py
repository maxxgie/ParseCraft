"""Tests for abstract syntax tree generation."""

from __future__ import annotations

import pytest

from core.ast import (
    ast_to_dict,
    count_ast_nodes,
    parse_tree_to_ast,
)
from core.topdown import analyze_topdown, simulate_topdown
from models.parse_tree import ParseTreeNode

LL1_GRAMMAR = """E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id"""


def _tree(text: str) -> ParseTreeNode:
    result = simulate_topdown(analyze_topdown(LL1_GRAMMAR, "LL(1)"), text)
    assert result.accepted, result.error
    return result.parse_tree


def test_none_root_returns_none():
    assert parse_tree_to_ast(None) is None


def test_unary_chain_collapses_to_leaf():
    ast = parse_tree_to_ast(_tree("id"))
    assert ast is not None
    # E -> T -> F -> id collapses to the operand leaf.
    assert ast.label == "id"
    assert ast.is_leaf()


def test_operator_is_lifted_to_label():
    ast = parse_tree_to_ast(_tree("id+id"))
    assert ast is not None
    labels = []

    def walk(node):
        labels.append(node.label)
        for child in node.children:
            walk(child)

    walk(ast)
    assert "+" in labels
    assert "*" not in labels


def test_multiplication_operator_present():
    ast = parse_tree_to_ast(_tree("id*id"))
    labels = []

    def walk(node):
        labels.append(node.label)
        for child in node.children:
            walk(child)

    walk(ast)
    assert "*" in labels


def test_ast_has_fewer_nodes_than_parse_tree():
    tree = _tree("id+id*id")
    ast = parse_tree_to_ast(tree)
    from core.parse_tree import count_nodes

    assert count_ast_nodes(ast) < count_nodes(tree)


def test_no_collapse_option_keeps_structure():
    tree = _tree("id")
    ast = parse_tree_to_ast(tree, collapse_unary=False, lift_operators=False)
    assert ast is not None
    assert count_ast_nodes(ast) > 1


def test_ast_to_dict_roundtrip():
    ast = parse_tree_to_ast(_tree("id+id"))
    data = ast_to_dict(ast)
    assert data["label"] == "E"
    assert isinstance(data["children"], list)


def test_epsilon_nodes_dropped():
    ast = parse_tree_to_ast(_tree("id"))
    labels = []

    def walk(node):
        labels.append(node.label)
        for child in node.children:
            walk(child)

    walk(ast)
    assert "ε" not in labels