"""Grammar analyzer panel: shows validation, ambiguity, and transform hints."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.grammar_analyzer import ERROR, INFO, WARNING, GrammarReport
from core.logging_config import get_logger

logger = get_logger(__name__)

_HEADERS = ["Level", "Code", "Message"]
_LEVEL_COLORS = {
    ERROR: (QColor("#FFCDD2"), QColor("#B71C1C")),
    WARNING: (QColor("#FFF3CD"), QColor("#8A6D00")),
    INFO: (QColor("#CFE2FF"), QColor("#0D47A1")),
}


class GrammarAnalyzerView(QWidget):
    """Tabular view of grammar analysis findings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see analysis results.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.table.setRowCount(0)
        self.header.setText("Generate a grammar to see analysis results.")
        self.header.setStyleSheet("color: #555;")

    def set_report(self, report: Optional[GrammarReport]) -> None:
        """Populate the view from a :class:`GrammarReport`."""
        self.table.setRowCount(0)
        if report is None:
            self.clear()
            return

        issues = report.issues
        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            bg, fg = _LEVEL_COLORS.get(issue.level, (None, None))
            cells = [issue.level, issue.code, issue.message]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if bg is not None:
                    item.setBackground(bg)
                if fg is not None:
                    item.setForeground(fg)
                self.table.setItem(row, col, item)

        if not issues:
            self.header.setText("No issues found — the grammar looks good.")
            self.header.setStyleSheet("color: #1E6B34;")
        else:
            color = "#B71C1C" if report.errors else "#8A6D00"
            self.header.setText(report.summary())
            self.header.setStyleSheet(f"color: {color};")