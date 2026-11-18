"""Conflict inspection and resolution display."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
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

from core.conflict_resolution import describe_conflict
from core.logging_config import get_logger
from gui.grammar_reference import GrammarReferencePane
from gui.palette import (
    RESOLVED_BG,
    RESOLVED_FG,
    UNRESOLVED_BG,
    UNRESOLVED_FG,
)

logger = get_logger(__name__)

_HEADERS = ["State", "Terminal", "Type", "Competing actions", "Resolution", "Strategy"]


def _cell(text: str, background=None, foreground=None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setToolTip(text)
    if background is not None:
        item.setBackground(background)
    if foreground is not None:
        item.setForeground(foreground)
    return item


class ConflictView(QWidget):
    """Tabular view of detected conflicts and how they were resolved."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see conflicts.")
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
        self.table.itemSelectionChanged.connect(self._show_detail)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Select a conflict to see the items, the reason, and a suggested "
            "resolution."
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([760, 360])
        layout.addWidget(splitter, 1)

        self._analysis = None
        self._conflicts = []

    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self._conflicts = []
        self.table.setRowCount(0)
        self.detail.clear()
        self.grammar.clear()
        self.header.setText("Generate a grammar to see conflicts.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the table from an analysis result."""
        self._analysis = analysis
        conflicts = analysis.conflicts
        self._conflicts = list(conflicts)
        resolutions = {(r.state, r.terminal): r for r in analysis.resolutions}
        self.detail.clear()
        self.grammar.set_from_analysis(analysis)

        self.table.setRowCount(len(conflicts))
        for row, conflict in enumerate(conflicts):
            resolution = resolutions.get((conflict.state, conflict.terminal))
            if resolution is not None:
                resolution_text = resolution.chosen.to_string()
                strategy_text = resolution.description
                background, foreground = RESOLVED_BG, RESOLVED_FG
            else:
                resolution_text = "unresolved"
                strategy_text = "-"
                background, foreground = UNRESOLVED_BG, UNRESOLVED_FG

            cells = [
                _cell(str(conflict.state), background, foreground),
                _cell(conflict.terminal, background, foreground),
                _cell(conflict.conflict_type, background, foreground),
                _cell(conflict.actions_summary(), background, foreground),
                _cell(resolution_text, background, foreground),
                _cell(strategy_text, background, foreground),
            ]
            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)

        if not conflicts:
            self.header.setText(
                f"{analysis.parser_type}: no conflicts detected "
                f"({analysis.table.num_states} states)."
            )
            self.header.setStyleSheet("color: #1E6B34;")
            return

        resolved = len(analysis.resolutions)
        unresolved = len(analysis.unresolved_conflicts)
        prec_note = ""
        if len(analysis.precedence) > 0:
            prec_note = f" Precedence declarations: {len(analysis.precedence)}."
        color = "#B00020" if unresolved else "#8A6D00"
        self.header.setText(
            f"{analysis.parser_type}: {len(conflicts)} conflict(s), "
            f"{resolved} resolved, {unresolved} unresolved.{prec_note}"
        )
        self.header.setStyleSheet(f"color: {color};")

    def _show_detail(self) -> None:
        """Show a full explanation for the selected conflict."""
        selection = self.table.selectionModel()
        rows = selection.selectedRows() if selection is not None else []
        if not rows:
            return
        row = rows[0].row()
        if self._analysis is None or row < 0 or row >= len(self._conflicts):
            return
        conflict = self._conflicts[row]
        self.detail.setPlainText(
            describe_conflict(
                conflict, self._analysis.automaton, self._analysis.parser_type
            )
        )