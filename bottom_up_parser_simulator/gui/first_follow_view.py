"""FIRST / FOLLOW set display."""

from __future__ import annotations

from typing import Set

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
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(mono)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # Side column with the grammar that produced these sets plus a sticky
        # explanation panel for the selected symbol.
        self.grammar = GrammarReferencePane(max_height=140)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Select a symbol to see how its FIRST / FOLLOW set was computed."
        )

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.addWidget(self.grammar, 0)
        right_layout.addWidget(self.detail, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([680, 360])
        layout.addWidget(splitter, 1)

        self._analysis = None
        self._rows: list[tuple[str, bool]] = []

    def clear(self) -> None:
        """Reset the view to its empty state."""
        self._analysis = None
        self._rows = []
        self.table.clearContents()
        self.table.setRowCount(0)
        self.grammar.clear()
        self.detail.clear()
        self.summary.setText("Generate a grammar to see FIRST/FOLLOW sets.")
        self.summary.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the table from an :class:`~core.engine.AnalysisResult`."""
        self._analysis = analysis
        first = analysis.first
        follow = analysis.follow
        non_terminals = sorted(analysis.grammar.non_terminals)
        terminals = sorted(analysis.grammar.terminals)
        self.grammar.set_grammar(analysis.grammar_text)

        rows = []
        for nt in non_terminals:
            rows.append((nt, True))
        for t in terminals:
            rows.append((t, False))
        self._rows = rows

        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row, (symbol, is_nt) in enumerate(rows):
            fset = first.get(symbol, set())
            folset = follow.get(symbol, set())
            sym_item = QTableWidgetItem(symbol)
            sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            first_item = QTableWidgetItem(_format_set(fset))
            follow_item = QTableWidgetItem(
                _format_set(folset) if folset or is_nt else "-"
            )
            if is_nt:
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
        if rows:
            self.table.selectRow(0)

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        selected = self.table.selectedIndexes()
        if not selected:
            return
        row = min(idx.row() for idx in selected)
        if 0 <= row < len(self._rows):
            self._show_symbol(self._rows[row][0])

    def _show_symbol(self, symbol: str) -> None:
        if self._analysis is None:
            return
        first = self._analysis.first.get(symbol, set())
        follow = self._analysis.follow.get(symbol, set())
        is_nt = symbol in self._analysis.grammar.non_terminals
        lines = [
            f"SYMBOL {symbol}",
            "=" * 48,
            "",
            "Kind:",
            "  non-terminal" if is_nt else "  terminal",
            "",
            f"FIRST({symbol}) =",
            "  " + (_format_set(first) if first else "{ }"),
            "",
            f"FOLLOW({symbol}) =",
        ]
        if is_nt:
            lines.append("  " + (_format_set(follow) if follow else "{ }"))
        else:
            lines.append("  n/a (terminals have no FOLLOW set)")
        self.detail.setPlainText("\n".join(lines))