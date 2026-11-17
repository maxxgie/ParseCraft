"""Abstract syntax tree viewer."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.ast import AstNode
from core.logging_config import get_logger

logger = get_logger(__name__)


class AstView(QWidget):
    """Displays an abstract syntax tree built from a parse tree."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel(
            "The abstract syntax tree appears here after a successful parse."
        )
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Abstract Syntax Tree"])
        self.tree.setColumnCount(1)
        layout.addWidget(self.tree, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.tree.clear()
        self.header.setText(
            "The abstract syntax tree appears here after a successful parse."
        )
        self.header.setStyleSheet("color: #555;")

    def set_ast(self, ast: Optional[AstNode]) -> None:
        """Populate the view from an :class:`AstNode` (or clear if ``None``)."""
        self.tree.clear()
        if ast is None:
            self.clear()
            return
        root = self._build(ast)
        self.tree.addTopLevelItem(root)
        self.tree.expandToDepth(1)
        self.header.setText(
            "Abstract syntax tree (grammar-only nodes removed; operators lifted)."
        )
        self.header.setStyleSheet("color: #1E6B34;")

    def _build(self, node: AstNode) -> QTreeWidgetItem:
        if node.is_leaf() and node.value:
            text = f"{node.label} ({node.value})"
        else:
            text = node.label
        item = QTreeWidgetItem([text])
        for child in node.children:
            item.addChild(self._build(child))
        return item