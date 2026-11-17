"""State validation report for the LR automaton."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.automaton import validate_automaton
from core.logging_config import get_logger
from core.table_validation import validate_parsing_table
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
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Select a check to see what was validated and why it passed or failed."
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([700, 360])
        layout.addWidget(splitter, 1)

        self._issues: list = []

    def clear(self) -> None:
        """Reset the view."""
        self._issues = []
        self.table.clearContents()
        self.table.setRowCount(0)
        self.grammar.clear()
        self.detail.clear()
        self.header.setText("Generate a grammar to validate the LR states.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Fill the table from an analysis result."""
        self.grammar.set_grammar(analysis.grammar_text)
        issues = validate_automaton(analysis.automaton) + validate_parsing_table(
            analysis
        )
        self._issues = list(issues)
        self.table.clearContents()
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            state_text = "-" if issue.state is None else f"I{issue.state}"
            status = "OK" if issue.ok else "FAIL"
            values = [state_text, issue.check, status, issue.detail]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.ItemDataRole.UserRole, row)
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
        if issues:
            self.table.selectRow(0)

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        selected = self.table.selectedIndexes()
        if not selected:
            return
        row = min(idx.row() for idx in selected)
        if 0 <= row < len(self._issues):
            self._show_issue(self._issues[row])

    def _show_issue(self, issue) -> None:
        state_text = "global" if issue.state is None else f"State {issue.state}"
        status = "PASS" if issue.ok else "FAIL"
        lines = [
            f"{issue.check} — {status}",
            "=" * 48,
            "",
            f"Scope: {state_text}",
            "",
        ]
        if issue.ok:
            lines.append("This check passed.")
        else:
            lines.append("This check FAILED.")
            if issue.detail:
                lines.append("")
                lines.append("Reason:")
                lines.append("")
                lines.append(f"  {issue.detail}")
        self.detail.setPlainText("\n".join(lines))