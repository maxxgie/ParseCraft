"""State validation report for the LR automaton."""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.automaton import validate_automaton
from core.logging_config import get_logger
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_HEADERS = ["State", "Check", "Status", "Detail"]

_OK_FG = QColor("#1B5E20")
_OK_BG = QColor("#E8F5E9")
_FAIL_FG = QColor("#B71C1C")
_FAIL_BG = QColor("#FFEBEE")


class ValidationView(QWidget):
    """Shows per-state validation of the canonical collection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to validate the LR states.")
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
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.table.setRowCount(0)
        self.grammar.clear()
        self.header.setText("Generate a grammar to validate the LR states.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Fill the table from an analysis result."""
        self.grammar.set_grammar(analysis.grammar_text)
        issues = validate_automaton(analysis.automaton)
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            state_text = "-" if issue.state is None else f"I{issue.state}"
            status = "OK" if issue.ok else "FAIL"
            values = [state_text, issue.check, status, issue.detail]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if col == 2:
                    if issue.ok:
                        item.setForeground(_OK_FG)
                        item.setBackground(_OK_BG)
                    else:
                        item.setForeground(_FAIL_FG)
                        item.setBackground(_FAIL_BG)
                self.table.setItem(row, col, item)

        failures = [issue for issue in issues if not issue.ok]
        if not failures:
            self.header.setText(
                f"Validation passed: {len(issues)} checks across "
                f"{len(analysis.automaton.states)} states."
            )
            self.header.setStyleSheet("color: #1E6B34;")
        else:
            self.header.setText(
                f"Validation failed: {len(failures)} of {len(issues)} checks."
            )
            self.header.setStyleSheet("color: #B00020;")