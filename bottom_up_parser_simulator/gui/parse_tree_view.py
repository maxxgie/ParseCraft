"""Parse-tree visualisation (indented text + graphical tree)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from core.parse_tree import collapse_unary_chains, tree_to_string
from gui.graph_canvas import GraphCanvas, GraphEdge, GraphNode
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

X_GAP = 90.0
Y_GAP = 72.0


def _compute_layout(
    root: ParseTreeNode,
) -> Tuple[Dict[int, Tuple[float, float]], List[Tuple[int, int]]]:
    """Compute (x, y) positions and edges for a tidy tree layout."""
    positions: Dict[int, Tuple[float, float]] = {}
    edges: List[Tuple[int, int]] = []
    next_leaf_x = [0.0]

    def place(node: ParseTreeNode, depth: int) -> float:
        node_id = id(node)
        if not node.children:
            x = next_leaf_x[0]
            next_leaf_x[0] += X_GAP
        else:
            xs = [place(child, depth + 1) for child in node.children]
            x = sum(xs) / len(xs)
        positions[node_id] = (x, depth * Y_GAP)
        return x

    def collect(node: ParseTreeNode) -> None:
        for child in node.children:
            edges.append((id(node), id(child)))
            collect(child)

    place(root, 0)
    collect(root)
    return positions, edges


class ParseTreeView(QWidget):
    """Shows the parse tree both as text and as a zoomable diagram."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root: Optional[ParseTreeNode] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Run a simulation to see the parse tree.")
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        controls = QHBoxLayout()
        self.collapse_cb = QCheckBox("Collapse single-child nodes")
        self.collapse_cb.setToolTip(
            "Hide grammar-only nodes (unit productions and single-child chains)."
        )
        self.collapse_cb.toggled.connect(self._rerender)
        controls.addWidget(self.collapse_cb)
        controls.addStretch(1)
        self.export_button = QPushButton("Export PNG...")
        self.export_button.clicked.connect(self._export_png)
        controls.addWidget(self.export_button)
        layout.addLayout(controls)

        self.tabs = QTabWidget()

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text_view.setFont(mono)
        self.tabs.addTab(self.text_view, "Text")

        self.canvas = GraphCanvas()
        self.tabs.addTab(self.canvas, "Graph")

        layout.addWidget(self.tabs, 1)

    def clear(self) -> None:
        """Reset the view."""
        self._root = None
        self.text_view.clear()
        self.canvas.render([], [])
        self.header.setText("Run a simulation to see the parse tree.")
        self.header.setStyleSheet("color: #555;")

    def show_message(self, message: str) -> None:
        """Show a non-tree message (e.g. a parse error)."""
        self._root = None
        self.text_view.setPlainText(message)
        self.canvas.render([], [])
        self.header.setText(message)
        self.header.setStyleSheet("color: #B00020;")

    def show_tree(self, root: Optional[ParseTreeNode]) -> None:
        """Render the given parse tree."""
        if root is None:
            self.show_message("(no parse tree)")
            return
        self._root = root
        self._render()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        if self._root is None:
            return
        display_root = self._root
        if self.collapse_cb.isChecked():
            display_root = collapse_unary_chains(self._root)
        self.text_view.setPlainText(tree_to_string(display_root))
        self._render_graph(display_root)
        self.header.setText(
            f"Parse tree: root '{self._root.symbol}'. "
            "Switch tabs to view text or graph."
        )
        self.header.setStyleSheet("color: #1E6B34;")

    def _render_graph(self, root: ParseTreeNode) -> None:
        positions, edges = _compute_layout(root)
        nodes: List[GraphNode] = []
        is_root = True
        stack = [root]
        while stack:
            node = stack.pop()
            node_id = id(node)
            x, y = positions[node_id]
            is_leaf = not node.children
            if is_root and node is root:
                kind = "root"
            elif is_leaf:
                kind = "terminal"
            else:
                kind = "nonterminal"
            label = node.value if is_leaf and node.value else node.symbol
            nodes.append(
                GraphNode(id=node_id, label=label, x=x, y=-y, kind=kind)
            )
            for child in node.children:
                stack.append(child)
        graph_edges = [GraphEdge(src=src, dst=dst) for src, dst in edges]
        self.canvas.render(nodes, graph_edges)

    def _rerender(self) -> None:
        if self._root is not None:
            self._render()

    def _export_png(self) -> None:
        if self._root is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Parse Tree", "parse_tree.png", "PNG Images (*.png)"
        )
        if not path:
            return
        ok = self.canvas.render_to_png(path)
        if ok:
            self.header.setText(f"Parse tree exported to {path}")
            self.header.setStyleSheet("color: #1E6B34;")