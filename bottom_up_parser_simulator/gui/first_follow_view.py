"""FIRST / FOLLOW set display."""

from __future__ import annotations

from typing import Set

from PyQt6.QtCore import Qt
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
from gui.settings import EPSILON

logger = get_logger(__name__)


def _format_set(values: Set[str]) -> str:
    """Format a set of symbols as ``{ a, b, c }``."""
    if not values:
        return "{ }"
    return "{ " + ", ".join(sorted(values)) + " }"


class FirstFollowView(QWidget):
    """A table showing FIRST and FOLLOW sets for each grammar symbol."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.summary = QLabel("Generate a grammar to see FIRST/FOLLOW sets.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #555;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Symbol", "FIRST", "FOLLOW"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Side column with the grammar that produced these sets. It has no
        # maximum height so it fills the table height for longer grammars.
        self.grammar = GrammarReferencePane(max_height=None)
        body = QHBoxLayout()
        body.addWidget(self.table, 1)
        body.addWidget(self.grammar, 0)
        layout.addLayout(body, 1)

    def clear(self) -> None:
        """Reset the view to its empty state."""
        self.table.setRowCount(0)
        self.grammar.clear()
        self.summary.setText("Generate a grammar to see FIRST/FOLLOW sets.")
        self.summary.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the table from an :class:`~core.engine.AnalysisResult`."""
        first = analysis.first
        follow = analysis.follow
        non_terminals = sorted(analysis.grammar.non_terminals)
        terminals = sorted(analysis.grammar.terminals)
        self.grammar.set_grammar(analysis.grammar_text)

        rows = []
        for nt in non_terminals:
            rows.append((nt, first.get(nt, set()), follow.get(nt, set())))
        for t in terminals:
            rows.append((t, first.get(t, {t}), set()))

        self.table.setRowCount(len(rows))
        for row, (symbol, fset, folset) in enumerate(rows):
            sym_item = QTableWidgetItem(symbol)
            sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            first_item = QTableWidgetItem(_format_set(fset))
            follow_item = QTableWidgetItem(
                _format_set(folset) if folset or symbol in non_terminals else "-"
            )
            if symbol in non_terminals:
                fnt = sym_item.font()
                fnt.setBold(True)
                sym_item.setFont(fnt)
            self.table.setItem(row, 0, sym_item)
            self.table.setItem(row, 1, first_item)
            self.table.setItem(row, 2, follow_item)

        self.summary.setText(
            f"{len(non_terminals)} non-terminals, {len(terminals)} terminals. "
            f"End marker is '$'; epsilon is '{EPSILON}'."
        )
        self.summary.setStyleSheet("color: #333;")