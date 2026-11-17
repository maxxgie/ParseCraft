"""Grammar analyzer panel: shows validation, ambiguity, and transform hints."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
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
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Select a finding to see the full explanation and any symbols involved."
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([700, 360])
        layout.addWidget(splitter, 1)

        self._report: Optional[GrammarReport] = None

    def clear(self) -> None:
        """Reset the view."""
        self._report = None
        self.table.clearContents()
        self.table.setRowCount(0)
        self.detail.clear()
        self.header.setText("Generate a grammar to see analysis results.")
        self.header.setStyleSheet("color: #555;")

    def set_report(self, report: Optional[GrammarReport]) -> None:
        """Populate the view from a :class:`GrammarReport`."""
        self.table.clearContents()
        self.table.setRowCount(0)
        self.detail.clear()
        self._report = report
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
                item.setData(Qt.ItemDataRole.UserRole, row)
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
            self.table.selectRow(0)

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        if self._report is None:
            return
        selected = self.table.selectedIndexes()
        if not selected:
            return
        row = min(idx.row() for idx in selected)
        issues = self._report.issues
        if 0 <= row < len(issues):
            self._show_issue(issues[row])

    def _show_issue(self, issue) -> None:
        lines = [
            f"{issue.level}: {issue.code}",
            "=" * 48,
            "",
            issue.message,
        ]
        symbols = getattr(issue, "symbols", None) or []
        if symbols:
            lines.append("")
            lines.append("Symbols involved:")
            lines.append("")
            lines.append("  " + ", ".join(symbols))
        self.detail.setPlainText("\n".join(lines))