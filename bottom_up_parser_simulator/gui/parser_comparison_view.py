"""Parser comparison panel: LL(1) vs LR(0)/SLR(1)/CLR(1)/LALR(1)."""

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

from core.comparison import ComparisonReport
from core.logging_config import get_logger

logger = get_logger(__name__)

_HEADERS = ["Parser", "States", "Table size", "Conflicts", "Status", "Notes"]


class ParserComparisonView(QWidget):
    """Table comparing parsing methods for the current grammar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to compare parsers.")
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
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.table.setRowCount(0)
        self.header.setText("Generate a grammar to compare parsers.")
        self.header.setStyleSheet("color: #555;")

    def set_report(self, report: Optional[ComparisonReport]) -> None:
        """Populate the view from a :class:`ComparisonReport`."""
        self.table.setRowCount(0)
        if report is None:
            self.clear()
            return

        stats = report.parser_stats
        self.table.setRowCount(len(stats))
        for row, s in enumerate(stats):
            for col, text in enumerate(s.as_row()):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if col == 4:  # status column colour
                    if s.conflict_free and s.compatible:
                        item.setForeground(QColor("#1B5E20"))
                    elif not s.compatible:
                        item.setForeground(QColor("#9E9E9E"))
                    else:
                        item.setForeground(QColor("#B71C1C"))
                self.table.setItem(row, col, item)

        self.header.setText(report.summary())
        self.header.setStyleSheet("color: #333;")