"""Parse-tree visualisation: Unicode text tree + interactive graph.

Layout::

    ┌─────────────────────────────────────────────┬───────────────────────┐
    │  [collapse]   zoom  -  +  fit   export …     │   Inspection panel    │
    ├─────────────────────────────────────────────┤   (production rule +  │
    │  Text │ Graph                                │    derivation step)   │
    │  ├── E                                       │                       │
    │  │   └── id                                   │                       │
    └─────────────────────────────────────────────┴───────────────────────┘

* The **Text** tab renders a fixed-width Unicode tree (``├──`` / ``└──`` /
  ``│``) with syntax-highlighted non-terminals, terminals and ε.
* The **Graph** tab renders rounded cards in a top-down layout with zoom
  controls; clicking a node highlights its whole subtree.
* Clicking a node in either view highlights its subtree and shows its
  production rule and derivation step in the inspection panel.
* Manual folding: double-click a text row (or use the buttons) to fold a node's
  children; the ``Collapse single-child nodes`` checkbox applies a global
  grammar-only collapse.
* Export to PNG / SVG / PDF at high resolution.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from core.parse_tree import build_display_tree, subtree_ids
from gui.graph_canvas import GraphCanvas, GraphEdge, GraphNode
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

X_GAP = 96.0
Y_GAP = 76.0

# --- palette ---------------------------------------------------------------
DEFAULT_FG = QColor("#334155")
NT_FG = QColor("#1E3A8A")        # non-terminal: bold blue
TERM_FG = QColor("#0F766E")      # terminal: teal
EPS_FG = QColor("#6B7280")       # epsilon: muted grey
MUTED_FG = QColor("#64748B")
HL_BG = QColor("#DBEAFE")        # selected-subtree background


def _mono_font(size: float = 10.0) -> QFont:
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(size)
    return font


def _compute_layout(
    entry: Tuple[ParseTreeNode, list],
) -> Tuple[Dict[int, Tuple[float, float]], List[Tuple[int, int]]]:
    """Compute (x, y) positions and edges for a tidy top-down tree layout."""
    positions: Dict[int, Tuple[float, float]] = {}
    edges: List[Tuple[int, int]] = []
    next_leaf_x = [0.0]

    def place(node: ParseTreeNode, children: list, depth: int) -> float:
        if not children:
            x = next_leaf_x[0]
            next_leaf_x[0] += X_GAP
        else:
            xs = [place(c[0], c[1], depth + 1) for c in children]
            x = sum(xs) / len(xs)
        positions[id(node)] = (x, depth * Y_GAP)
        for child_node, _ in children:
            edges.append((id(node), id(child_node)))
        return x

    place(entry[0], entry[1], 0)
    return positions, edges


class ParseTreeView(QWidget):
    """Shows the parse tree as Unicode text and as a zoomable diagram."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root: Optional[ParseTreeNode] = None
        self._folded: Set[int] = set()
        self._current_key: Optional[int] = None
        self._text_block_keys: List[int] = []
        self._node_by_key: Dict[int, ParseTreeNode] = {}
        self._visible_keys: Set[int] = set()
        self._suppress_text_signal = False
        self._text_size = 10.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Run a simulation to see the parse tree.")
        self.header.setStyleSheet("color: #555;")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        # --- controls -------------------------------------------------
        controls = QHBoxLayout()
        self.collapse_cb = QCheckBox("Collapse single-child nodes")
        self.collapse_cb.setToolTip(
            "Hide grammar-only nodes (unit productions and single-child chains)."
        )
        self.collapse_cb.toggled.connect(self._rerender)
        controls.addWidget(self.collapse_cb)
        controls.addSpacing(12)

        self.zoom_out_btn = QPushButton("Zoom −")
        self.zoom_out_btn.setToolTip("Zoom the graph out")
        self.zoom_out_btn.clicked.connect(self.canvas_zoom_out)
        controls.addWidget(self.zoom_out_btn)

        self.zoom_in_btn = QPushButton("Zoom +")
        self.zoom_in_btn.setToolTip("Zoom the graph in")
        self.zoom_in_btn.clicked.connect(self.canvas_zoom_in)
        controls.addWidget(self.zoom_in_btn)

        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setToolTip("Fit the whole graph in the view")
        self.fit_btn.clicked.connect(self.canvas_fit)
        controls.addWidget(self.fit_btn)

        controls.addStretch(1)

        self.export_button = QPushButton("Export PNG…")
        self.export_button.clicked.connect(lambda: self._export("png"))
        controls.addWidget(self.export_button)
        self.export_svg_button = QPushButton("SVG")
        self.export_svg_button.clicked.connect(lambda: self._export("svg"))
        controls.addWidget(self.export_svg_button)
        self.export_pdf_button = QPushButton("PDF")
        self.export_pdf_button.clicked.connect(lambda: self._export("pdf"))
        controls.addWidget(self.export_pdf_button)
        layout.addLayout(controls)

        # --- main area: tabs + inspection -----------------------------
        self.tabs = QTabWidget()

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.text_view.setFont(_mono_font(self._text_size))
        self.text_view.setPlaceholderText(
            "The parse tree appears here. Click a row to inspect it; "
            "double-click to fold/unfold its children."
        )
        self.text_view.viewport().installEventFilter(self)
        self.text_view.cursorPositionChanged.connect(self._on_text_cursor)
        self.tabs.addTab(self.text_view, "Text")

        self.canvas = GraphCanvas()
        self.canvas.node_selected.connect(self._on_graph_node_selected)
        self.canvas.viewport().installEventFilter(self)
        self.tabs.addTab(self.canvas, "Graph")

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setFont(_mono_font(9.5))
        self.detail.setPlaceholderText(
            "Select a node in the Text or Graph view to see its production "
            "rule and derivation step."
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([720, 320])
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Public API (used by MainWindow)
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the view."""
        self._root = None
        self._folded.clear()
        self._current_key = None
        self._text_block_keys = []
        self._node_by_key = {}
        self._visible_keys = set()
        self.text_view.clear()
        self.canvas.render([], [])
        self.detail.clear()
        self.header.setText("Run a simulation to see the parse tree.")
        self.header.setStyleSheet("color: #555;")

    def show_message(self, message: str) -> None:
        """Show a non-tree message (e.g. a parse error)."""
        self._root = None
        self._folded.clear()
        self._current_key = None
        self._node_by_key = {}
        self._text_block_keys = []
        self.text_view.setPlainText(message)
        self.canvas.render([], [])
        self.detail.clear()
        self.header.setText(message)
        self.header.setStyleSheet("color: #B00020;")

    def show_tree(self, root: Optional[ParseTreeNode]) -> None:
        """Render the given parse tree."""
        if root is None:
            self.show_message("(no parse tree)")
            return
        self._root = root
        self._folded.clear()
        self._current_key = None
        self._render()

    # ------------------------------------------------------------------
    # Zoom slots (graph)
    # ------------------------------------------------------------------
    def canvas_zoom_in(self) -> None:
        self.canvas.zoom_in()

    def canvas_zoom_out(self) -> None:
        self.canvas.zoom_out()

    def canvas_fit(self) -> None:
        self.canvas.fit_view()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _display_entry(self):
        return build_display_tree(
            self._root, collapse=self.collapse_cb.isChecked(), folded=self._folded
        )

    def _rerender(self) -> None:
        if self._root is not None:
            self._render()

    def _render(self) -> None:
        if self._root is None:
            return
        entry = self._display_entry()

        # Rebuild node index + visible set.
        self._node_by_key = {}
        self._visible_keys = set()

        def index(node, children):
            self._node_by_key[id(node)] = node
            self._visible_keys.add(id(node))
            for c in children:
                index(c[0], c[1])

        if entry is not None:
            index(entry[0], entry[1])

        # If the current selection is no longer visible, fall back to root.
        if self._current_key is not None and self._current_key not in self._visible_keys:
            self._current_key = None
        if self._current_key is None and self._root is not None:
            self._current_key = id(self._root) if id(self._root) in self._visible_keys else None

        self._render_text(entry)
        self._render_graph(entry)
        self._apply_selection_highlight()

        depth = self._tree_depth(self._root)
        count = self._count_nodes(self._root)
        suffix = "  (single-child collapsed)" if self.collapse_cb.isChecked() else ""
        self.header.setText(
            f"Parse tree: root '{self._root.symbol}' — {count} nodes, "
            f"depth {depth}.{suffix} Click to inspect; double-click a node to fold."
        )
        self.header.setStyleSheet("color: #1E6B34;")

    # ---- Text view ----------------------------------------------------
    def _render_text(self, entry) -> None:
        self._suppress_text_signal = True
        self.text_view.setUpdatesEnabled(False)
        self.text_view.clear()
        self._text_block_keys = []

        cursor = self.text_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        def fmt(color: QColor, bold=False, italic=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(color)
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            if italic:
                f.setFontItalic(True)
            return f

        def emit_line(prefix: str, node: ParseTreeNode) -> None:
            if self._text_block_keys:
                cursor.insertBlock()
            self._text_block_keys.append(id(node))
            cursor.insertText(prefix, fmt(DEFAULT_FG))
            # Label segments.
            if node.is_leaf():
                if node.symbol == "ε":
                    cursor.insertText("ε", fmt(EPS_FG, italic=True))
                else:
                    cursor.insertText(node.symbol, fmt(TERM_FG, bold=True))
                    if node.value and node.value != node.symbol:
                        cursor.insertText(f" ({node.value})", fmt(MUTED_FG))
            else:
                cursor.insertText(node.symbol, fmt(NT_FG, bold=True))

        def walk(node, children, prefix, is_last, is_root):
            if is_root:
                connector = ""
            else:
                connector = "└── " if is_last else "├── "
            emit_line(prefix + connector, node)
            if children:
                new_prefix = prefix + ("" if is_root else ("    " if is_last else "│   "))
                for i, (child_node, grand) in enumerate(children):
                    walk(
                        child_node,
                        grand,
                        new_prefix,
                        i == len(children) - 1,
                        False,
                    )

        if entry is not None:
            walk(entry[0], entry[1], "", True, True)
        else:
            self.text_view.setPlainText("(empty parse tree)")

        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_view.setTextCursor(cursor)
        self.text_view.setUpdatesEnabled(True)
        self.text_view.setExtraSelections([])
        self._suppress_text_signal = False

    def _apply_text_highlight(self) -> None:
        """Highlight the selected subtree's rows via extra selections."""
        selected = self._selected_subtree()
        selections = []
        if selected:
            doc = self.text_view.document()
            for block_no, key in enumerate(self._text_block_keys):
                if key not in selected:
                    continue
                block = doc.findBlockByNumber(block_no)
                if not block.isValid():
                    continue
                es = QTextEdit.ExtraSelection()
                es.format.setBackground(HL_BG)
                es.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                es.cursor = QTextCursor(block)
                selections.append(es)
        self.text_view.setExtraSelections(selections)

    # ---- Graph view ---------------------------------------------------
    def _render_graph(self, entry) -> None:
        if entry is None:
            self.canvas.render([], [])
            return
        positions, edges = _compute_layout(entry)

        nodes: List[GraphNode] = []
        stack = [(entry[0], entry[1])]
        while stack:
            node, children = stack.pop()
            is_leaf = not children
            if node is self._root:
                kind = "root"
            elif is_leaf:
                kind = "terminal"
            else:
                kind = "nonterminal"
            if is_leaf and node.symbol == "ε":
                label = "ε"
            elif is_leaf and node.value and node.value != node.symbol:
                label = f"{node.symbol} ({node.value})"
            elif is_leaf:
                label = node.value or node.symbol
            else:
                label = node.symbol

            tip = ""
            if not is_leaf:
                if id(node) in self._folded:
                    label += " …"
                    tip = "Double-click to unfold children"
                else:
                    tip = "Double-click to fold children"
            x, y = positions[id(node)]
            nodes.append(
                GraphNode(
                    id=id(node), label=label, x=x, y=y, kind=kind, tip=tip
                )
            )
            for child_node, grand in children:
                stack.append((child_node, grand))

        graph_edges = [GraphEdge(src=src, dst=dst) for src, dst in edges]
        self.canvas.render(nodes, graph_edges)

    # ---- selection ----------------------------------------------------
    def _selected_subtree(self) -> Set[int]:
        if self._current_key is None:
            return set()
        node = self._node_by_key.get(self._current_key)
        if node is None:
            return set()
        return subtree_ids(node) & self._visible_keys

    def _apply_selection_highlight(self) -> None:
        self._apply_text_highlight()
        self.canvas.set_highlight(self._selected_subtree())
        if self._current_key is not None:
            self._show_inspection(self._node_by_key.get(self._current_key))
        else:
            self.detail.clear()

    def _select_key(self, key: int) -> None:
        if key not in self._visible_keys:
            return
        self._current_key = key
        self._apply_selection_highlight()

    def _on_text_cursor(self) -> None:
        if self._suppress_text_signal:
            return
        block = self.text_view.textCursor().blockNumber()
        if 0 <= block < len(self._text_block_keys):
            self._select_key(self._text_block_keys[block])

    def _on_graph_node_selected(self, key: object) -> None:
        self._select_key(key)

    # ---- inspection ---------------------------------------------------
    def _show_inspection(self, node: Optional[ParseTreeNode]) -> None:
        if node is None:
            return
        self.detail.setPlainText(self._inspection_text(node))

    def _inspection_text(self, node: ParseTreeNode) -> str:
        lines: List[str] = []
        if node.is_leaf():
            if node.symbol == "ε":
                lines.append("ε  (epsilon production)")
                lines.append("")
                lines.append("This node derives the empty string.")
            else:
                lines.append(f"Terminal: {node.symbol}")
                if node.value and node.value != node.symbol:
                    lines.append(f"Matched input: '{node.value}'")
                lines.append("")
                lines.append("Leaf nodes match a single input token.")
        else:
            children = node.children
            rhs = " ".join(c.symbol for c in children) if children else "ε"
            lines.append("Production:")
            lines.append(f"  {node.symbol} → {rhs}")
            lines.append("")
            lines.append(f"{len(children)} child node(s).")

        # Derivation path (root → node).
        path: List[ParseTreeNode] = []
        cur: Optional[ParseTreeNode] = node
        while cur is not None:
            path.append(cur)
            cur = cur.parent
        path.reverse()
        lines.append("")
        lines.append(f"Depth: {len(path) - 1}")
        lines.append("")
        lines.append("Derivation (root → this node):")
        lines.append("  " + " ⇒ ".join(p.symbol for p in path))

        # Subtree size.
        lines.append("")
        lines.append(f"Subtree size: {len(subtree_ids(node))} node(s)")
        return "\n".join(lines)

    # ---- manual folding ----------------------------------------------
    def _toggle_fold(self, key: int) -> bool:
        """Toggle folding at ``key`` if it is a non-leaf node; return success."""
        node = self._node_by_key.get(key)
        if node is None or node.is_leaf():
            return False
        if key in self._folded:
            self._folded.discard(key)
        else:
            self._folded.add(key)
        self._render()
        return True

    def eventFilter(self, obj, event):  # noqa: N802 (Qt naming)
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj is self.text_view.viewport():
                pos = event.position().toPoint()
                block = self.text_view.cursorForPosition(pos).blockNumber()
                if 0 <= block < len(self._text_block_keys):
                    self._toggle_fold(self._text_block_keys[block])
                return True
            if obj is self.canvas.viewport():
                key = self.canvas.node_id_at(event.position().toPoint())
                if key is not None:
                    self._toggle_fold(key)
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export(self, fmt: str) -> None:
        if self._root is None:
            return
        ext = fmt
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Parse Tree ({fmt.upper()})",
            f"parse_tree.{ext}",
            {
                "png": "PNG Images (*.png)",
                "svg": "SVG Images (*.svg)",
                "pdf": "PDF Documents (*.pdf)",
            }[fmt],
        )
        if not path:
            return
        ok = self.canvas.render_to_file(path, fmt)
        if ok:
            self.header.setText(f"Parse tree exported to {path}")
            self.header.setStyleSheet("color: #1E6B34;")
        else:
            self.header.setText("Nothing to export (the tree is empty).")
            self.header.setStyleSheet("color: #B00020;")

    # ------------------------------------------------------------------
    @staticmethod
    def _tree_depth(node: Optional[ParseTreeNode]) -> int:
        if node is None:
            return 0
        if not node.children:
            return 1
        return 1 + max(ParseTreeView._tree_depth(c) for c in node.children)

    @staticmethod
    def _count_nodes(node: Optional[ParseTreeNode]) -> int:
        if node is None:
            return 0
        return 1 + sum(ParseTreeView._count_nodes(c) for c in node.children)