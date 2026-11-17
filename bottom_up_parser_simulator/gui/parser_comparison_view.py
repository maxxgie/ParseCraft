"""Grammar compatibility panel: LL(1) vs LR(0)/SLR(1)/CLR(1)/LALR(1)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.comparison import (
    STATUS_COMPATIBLE,
    STATUS_INCOMPATIBLE,
    ComparisonReport,
)
from core.logging_config import get_logger
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_HEADERS = ["Parser", "Status", "Reason"]

_STATUS_COLORS = {
    STATUS_COMPATIBLE: (QColor("#1B5E20"), QColor("#E8F5E9")),
    STATUS_INCOMPATIBLE: (QColor("#B71C1C"), QColor("#FFEBEE")),
}


class ParserComparisonView(QWidget):
    """Compatibility table with per-parser explanations.

    Selecting a parser shows *why* it is or is not compatible, including the
    grammar property that causes the result.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see parser compatibility.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        self._report: Optional[ComparisonReport] = None

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
        self.table.itemSelectionChanged.connect(self._show_explanation)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Select a parser to see why it is or is not compatible."
        )
        self.detail.setMaximumHeight(150)
        layout.addWidget(self.detail, 0)

    def clear(self) -> None:
        """Reset the view."""
        self._report = None
        self.table.setRowCount(0)
        self.detail.clear()
        self.grammar.clear()
        self.header.setText("Generate a grammar to see parser compatibility.")
        self.header.setStyleSheet("color: #555;")

    def set_report(self, report: Optional[ComparisonReport]) -> None:
        """Populate the view from a :class:`ComparisonReport`."""
        self._report = report
        self.table.setRowCount(0)
        self.detail.clear()
        if report is None:
            self.clear()
            return

        self.grammar.set_grammar(report.grammar_text)
        stats = report.parser_stats
        self.table.setRowCount(len(stats))
        for row, s in enumerate(stats):
            for col, text in enumerate(s.as_row()):
                item = QTableWidgetItem(text)
                item.setToolTip(s.explanation)
                if col == 1:
                    foreground, background = _STATUS_COLORS.get(
                        s.status, (QColor("#333"), QColor("#FFFFFF"))
                    )
                    item.setForeground(foreground)
                    item.setBackground(background)
                self.table.setItem(row, col, item)

        self.header.setText(report.summary())
        self.header.setStyleSheet("color: #333;")
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _show_explanation(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        row = rows[0].row()
        parser_item = self.table.item(row, 0)
        if parser_item is None:
            return
        stats = {s.parser: s for s in self._current_stats()}
        entry = stats.get(parser_item.text())
        if entry is None:
            return
        status = entry.status
        lines = [
            f"{entry.parser}: {status.upper()}",
            "",
            entry.explanation,
        ]
        if entry.conflicts:
            lines.append("")
            lines.append(f"Conflicts: {entry.conflicts}")
        if entry.num_states is not None:
            lines.append(f"States: {entry.num_states}")
        self.detail.setPlainText("\n".join(lines))

    def _current_stats(self):
        report = getattr(self, "_report", None)
        return report.parser_stats if report is not None else []