"""LR item listing: every item of every state, with production numbers."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_HEADERS = ["State", "Production #", "LR Item"]


class LRItemsView(QWidget):
    """Tabular view of all LR items in the canonical collection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see LR items.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")

        self.grammar = GrammarReferencePane()
        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.table.setRowCount(0)
        self.grammar.clear()
        self.header.setText("Generate a grammar to see LR items.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Fill the table from an analysis result."""
        automaton = analysis.automaton
        self.grammar.set_grammar(analysis.grammar_text)

        rows = []
        for state in automaton.states:
            for item in state.sorted_items():
                number = state.production_order.get((item.lhs, item.rhs), "")
                rows.append((str(state.state_id), str(number), item.to_string()))

        self.table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))

        self.header.setText(
            f"{analysis.parser_type}: {len(automaton.states)} states, "
            f"{len(rows)} LR items."
        )
        self.header.setStyleSheet("color: #333;")