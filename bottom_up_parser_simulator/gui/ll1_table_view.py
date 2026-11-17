"""LL(1) predictive parsing table view."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from core.parser_registry import procedure_trace_kind, uses_parse_table
from core.topdown.ll1 import EPSILON, explain_ll1_cell, validate_ll1_table
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_CONFLICT_BG = QColor("#FFCDD2")
_CONFLICT_FG = QColor("#B71C1C")
_ENTRY_BG = QColor("#E8F5E9")
_ENTRY_FG = QColor("#1B5E20")


def _cell(text: str, background=None, foreground=None, bold: bool = False):
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setToolTip(text)
    if background is not None:
        item.setBackground(background)
    if foreground is not None:
        item.setForeground(foreground)
    mono = QFont("Consolas")
    mono.setStyleHint(QFont.StyleHint.Monospace)
    mono.setBold(bold)
    item.setFont(mono)
    return item


class LL1TableView(QWidget):
    """Displays the LL(1) predictive table M[Non-terminal, Terminal].

    * *full* mode shows every non-terminal row and terminal column;
    * *compact* mode hides rows/columns that contain no entry.

    Clicking a cell explains why the production is there (or reports the
    FIRST/FIRST or FIRST/FOLLOW conflict and a suggested fix).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate an LL(1) grammar to see its table.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")

        self.grammar = GrammarReferencePane()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (non-terminal, terminal...)")
        self.search.setClearButtonEnabled(True)
        self.compact_cb = QCheckBox("Compact view")
        self.compact_cb.setToolTip("Hide rows and columns that contain no entry.")
        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        top_row.addWidget(self.search, 0)
        top_row.addWidget(self.compact_cb, 0)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 0)
        self.table.verticalHeader().setVisible(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        self.table.cellClicked.connect(self._on_cell_clicked)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Click a cell to see which production generated it and why."
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([780, 360])
        layout.addWidget(splitter, 1)

        self._result = None
        self._shown_nts: list[str] = []
        self._shown_terms: list[str] = []
        self._issues: dict[tuple[str, str], object] = {}

        self.compact_cb.toggled.connect(lambda _=None: self._render())
        self.search.textChanged.connect(lambda _=None: self._apply_search())

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the view."""
        self._result = None
        self._shown_nts = []
        self._shown_terms = []
        self._issues = {}
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.detail.clear()
        self.grammar.clear()
        self.header.setText("Generate an LL(1) grammar to see its table.")
        self.header.setStyleSheet("color: #555;")

    def set_analysis(self, result: Optional[object]) -> None:
        """Attach (or clear) the top-down analysis whose LL(1) table to show."""
        self._result = result
        self._render()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        result = self._result
        if result is None:
            self.clear()
            return

        self.grammar.set_grammar(result.grammar_text)
        table = getattr(result, "ll1_table", None)
        if table is None:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self._shown_nts = []
            self._shown_terms = []
            self._issues = {}
            self.header.setText(
                f"{result.method}: this parser is procedure-based, so it has no "
                f"parse table — it displays {procedure_trace_kind(result.method)} "
                "instead."
                if not uses_parse_table(result.method)
                else f"{result.method}: the LL(1) table could not be generated."
            )
            self.header.setStyleSheet("color: #555;")
            return

        issues = validate_ll1_table(table, result.grammar, result.first, result.follow)
        self._issues = {(i.nonterminal, i.terminal): i for i in issues}

        compact = self.compact_cb.isChecked()
        nonterminals = list(table.non_terminals)
        terminals = list(table.terminals)

        if compact:
            shown_nts = [
                nt for nt in nonterminals
                if any(table.cell(nt, t) for t in terminals)
            ]
            shown_terms = [
                t for t in terminals
                if any(table.cell(nt, t) for nt in nonterminals)
            ]
        else:
            shown_nts = nonterminals
            shown_terms = terminals

        self._shown_nts = shown_nts
        self._shown_terms = shown_terms

        self.table.clear()
        self.table.setColumnCount(len(shown_terms) + 1)
        self.table.setHorizontalHeaderLabels(["Non-terminal", *shown_terms])
        self.table.setRowCount(len(shown_nts))
        self.table.setVerticalHeaderLabels(shown_nts)

        for row, nt in enumerate(shown_nts):
            for col, terminal in enumerate(shown_terms, start=1):
                indices = list(dict.fromkeys(table.cell(nt, terminal)))
                if not indices:
                    self.table.setItem(row, col, _cell(""))
                    continue
                text = " | ".join(
                    self._production_text(table.productions[i][1]) for i in indices
                )
                if (nt, terminal) in self._issues:
                    cell = _cell(text, _CONFLICT_BG, _CONFLICT_FG, bold=True)
                else:
                    cell = _cell(text, _ENTRY_BG, _ENTRY_FG)
                self.table.setItem(row, col, cell)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

        if issues:
            self.header.setText(
                f"{result.method}: LL(1) table with {len(issues)} conflict(s). "
                "Click a red cell to see the reason and suggested fix."
            )
            self.header.setStyleSheet("color: #B00020;")
        else:
            self.header.setText(
                f"{result.method}: LL(1) table is conflict-free "
                f"({len(nonterminals)} rows, {len(terminals)} columns)."
            )
            self.header.setStyleSheet("color: #1E6B34;")

        self._apply_search()

    def _apply_search(self) -> None:
        """Hide rows whose visible cells do not match the search text."""
        text = self.search.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            match = False
            header_item = self.table.verticalHeaderItem(row)
            if header_item is not None and text in header_item.text().lower():
                match = True
            if not match:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is not None and text in item.text().lower():
                        match = True
                        break
            self.table.setRowHidden(row, not match)

    @staticmethod
    def _production_text(body) -> str:
        return " ".join(body) if body else EPSILON

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if self._result is None or col == 0:
            self.detail.clear()
            return
        if not (0 <= row < len(self._shown_nts)):
            return
        term_index = col - 1
        if not (0 <= term_index < len(self._shown_terms)):
            return
        nt = self._shown_nts[row]
        terminal = self._shown_terms[term_index]
        issue = self._issues.get((nt, terminal))
        if issue is not None:
            self.detail.setPlainText(issue.message())
            return
        table = self._result.ll1_table
        self.detail.setPlainText(
            explain_ll1_cell(
                table,
                self._result.grammar,
                nt,
                terminal,
                self._result.first,
                self._result.follow,
            )
        )