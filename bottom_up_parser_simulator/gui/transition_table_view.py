"""State-transition table view (Configuration / Consume / Next State)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.automaton import transition_rows
from core.logging_config import get_logger

logger = get_logger(__name__)

COLUMNS = ["State", "Configuration State", "Consume", "Next State"]


class TransitionTableView(QWidget):
    """Textbook-style state-transition table for the LR automaton."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see the transition table.")
        self.header.setStyleSheet("color: #555;")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the table."""
        self.table.setRowCount(0)
        self.header.setText("Generate a grammar to see the transition table.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Fill the table from an analysis result."""
        automaton = analysis.automaton
        rows = transition_rows(automaton)
        self.table.setRowCount(len(rows))
        for row_index, (state, configuration, consume, target) in enumerate(rows):
            values = [
                str(state),
                configuration,
                consume,
                "" if target is None else str(target),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))
        self.header.setText(
            f"{analysis.parser_type}: {len(automaton.states)} states, "
            f"{len(automaton.transitions)} transitions."
        )
        self.header.setStyleSheet("color: #333;")