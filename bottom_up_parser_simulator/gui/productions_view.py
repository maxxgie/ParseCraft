"""Numbered production display (augmented grammar)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger

logger = get_logger(__name__)


class ProductionsView(QWidget):
    """Shows the augmented grammar with production numbers.

    The numbers match the ``Rn`` entries used in ACTION tables and reductions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see numbered productions.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Number", "Production"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.table.setRowCount(0)
        self.header.setText("Generate a grammar to see numbered productions.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Fill the table from the analysis's augmented grammar."""
        augmented = getattr(analysis.automaton, "augmented_grammar", None)
        productions = (
            augmented.productions if augmented is not None else analysis.grammar.productions
        )
        rows = []
        for lhs, bodies in productions.items():
            for body in bodies:
                text = f"{lhs} -> {' '.join(body) if body else 'ε'}"
                rows.append(text)

        self.table.setRowCount(len(rows))
        for index, text in enumerate(rows):
            number_item = QTableWidgetItem(f"({index})")
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            prod_item = QTableWidgetItem(text)
            prod_item.setToolTip(text)
            self.table.setItem(index, 0, number_item)
            self.table.setItem(index, 1, prod_item)

        self.header.setText(
            f"{analysis.parser_type}: {len(rows)} productions "
            "(0 is the augmented start production)."
        )
        self.header.setStyleSheet("color: #333;")