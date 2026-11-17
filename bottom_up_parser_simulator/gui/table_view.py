"""Combined ACTION / GOTO parsing-table display."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from core.table_explain import explain_action, explain_goto
from gui.grammar_reference import GrammarReferencePane
from gui.palette import (
    BLANK_BG,
    BLANK_FG,
    ERROR_BG,
    ERROR_FG,
    GOTO_BG,
    GOTO_FG,
    action_colors,
)

logger = get_logger(__name__)

# Neutral colour for the thin divider that separates ACTION from GOTO.
DIVIDER_BG = QColor("#CFD8DC")


def _cell(
    text: str, background=None, foreground=None, bold: bool = False
) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if background is not None:
        item.setBackground(background)
    if foreground is not None:
        item.setForeground(foreground)
    if bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    return item


def _verbose_action(action) -> str:
    """Render an action verbosely (``SHIFT 5`` / ``REDUCE ...`` / ``ACCEPT``)."""
    if action.action_type == "shift":
        return f"SHIFT {action.state}"
    if action.action_type == "reduce":
        body = action.production_rhs or ()
        text = " ".join(body) if body else "ε"
        return f"REDUCE {action.production_lhs} -> {text} (r{action.rule_number})"
    if action.action_type == "accept":
        return "ACCEPT"
    return action.to_string()


class CombinedTableView(QWidget):
    """Combined ACTION/GOTO parsing table.

    Terminals (ACTION) are shown first, then a thin divider, then
    non-terminals (GOTO), matching the classic single-table layout used in
    compiler-construction textbooks.

    Two display modes are provided:

    * *full* (default) — the grid with every terminal and non-terminal column;
    * *compact* — a per-state list of only the entries that actually exist.

    Clicking any ACTION or GOTO cell shows a full explanation of where the
    entry came from (the responsible LR item and the DFA transition).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see the ACTION/GOTO table.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")

        self.grammar = GrammarReferencePane()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (shift, R2, state...)")
        self.search.setClearButtonEnabled(True)
        self.compact_cb = QCheckBox("Compact view")
        self.compact_cb.setToolTip(
            "Show only the ACTION/GOTO entries that exist, one state at a time."
        )
        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        top_row.addWidget(self.search, 0)
        top_row.addWidget(self.compact_cb, 0)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 0)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellClicked.connect(self._on_cell_clicked)

        self.compact_text = QPlainTextEdit()
        self.compact_text.setReadOnly(True)
        self.compact_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.compact_text.setVisible(False)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setPlaceholderText(
            "Click an ACTION or GOTO cell to see which LR item and transition "
            "produced it."
        )

        # Left column stacks the grid and the compact listing; right column
        # holds the sticky explanation panel.
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.table, 1)
        left_layout.addWidget(self.compact_text, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([780, 360])
        layout.addWidget(splitter, 1)

        self._analysis = None
        self._terminals: list[str] = []
        self._non_terminals: list[str] = []
        self._divider_col = -1
        self._goto_start = -1
        self._row_text: list[str] = []

        self.compact_cb.toggled.connect(self._on_compact_toggled)
        self.search.textChanged.connect(lambda _=None: self._apply_search())

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the table."""
        self._analysis = None
        self._terminals = []
        self._non_terminals = []
        self._row_text = []
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.compact_text.clear()
        self.detail.clear()
        self.grammar.clear()
        self.header.setText("Generate a grammar to see the ACTION/GOTO table.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis, show_errors: bool = False) -> None:
        """Fill the combined ACTION/GOTO table.

        Args:
            analysis: The analysis result to display.
            show_errors: When ``True``, empty ACTION cells read ``Error``
                instead of being left blank.
        """
        self._analysis = analysis
        table = analysis.table
        self.grammar.set_grammar(analysis.grammar_text)

        terminals = list(table.terminals)
        non_terminals = list(table.non_terminals)
        self._terminals = terminals
        self._non_terminals = non_terminals
        self._row_text = []
        self._divider_col = 1 + len(terminals)
        self._goto_start = self._divider_col + 1

        headers = ["State", *terminals, "", *non_terminals]
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(table.num_states)

        divider_header = self.table.horizontalHeaderItem(self._divider_col)
        if divider_header is not None:
            divider_header.setBackground(DIVIDER_BG)
            divider_header.setText("")

        for state in range(table.num_states):
            state_item = QTableWidgetItem(str(state))
            state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(state, 0, state_item)
            parts: list[str] = [str(state)]

            for col, terminal in enumerate(terminals, start=1):
                action = table.get_action(state, terminal)
                if action is None:
                    if show_errors:
                        cell = _cell("Error", ERROR_BG, ERROR_FG)
                    else:
                        cell = _cell("", BLANK_BG, BLANK_FG)
                else:
                    bg, fg = action_colors(action.action_type)
                    bold = action.action_type == "accept"
                    cell = _cell(action.to_string(), bg, fg, bold=bold)
                    parts.append(action.to_string())
                    parts.append(_verbose_action(action))
                self.table.setItem(state, col, cell)

            self.table.setItem(
                state, self._divider_col, _cell("", DIVIDER_BG, DIVIDER_BG)
            )

            for col, nt in enumerate(non_terminals, start=self._goto_start):
                target = table.get_goto(state, nt)
                if target is not None:
                    cell = _cell(str(target), GOTO_BG, GOTO_FG, bold=True)
                    parts.append(str(target))
                else:
                    cell = _cell("", BLANK_BG, BLANK_FG)
                self.table.setItem(state, col, cell)

            self._row_text.append(" ".join(parts).lower())

        self.table.setColumnWidth(self._divider_col, 6)
        self.compact_text.setPlainText(self._compact_text())
        self._on_compact_toggled(self.compact_cb.isChecked())
        self._apply_search()

        conflicts = len(analysis.conflicts)
        resolved = len(analysis.resolutions)
        note = f" — {conflicts} conflict(s), {resolved} resolved" if conflicts else ""
        self.header.setText(
            f"{analysis.parser_type}: ACTION/GOTO table "
            f"({table.num_states} states){note}. "
            "ACTION = terminals (blue shift, green reduce); "
            "GOTO = non-terminals (lavender). Click a cell for details."
        )
        self.header.setStyleSheet("color: #333;")

    # ------------------------------------------------------------------
    def _compact_text(self) -> str:
        """Return the compact per-state ACTION/GOTO listing."""
        if self._analysis is None:
            return ""
        table = self._analysis.table
        lines: list[str] = ["ACTION"]
        for state in range(table.num_states):
            entries = [
                f"  {terminal} : {_verbose_action(table.get_action(state, terminal))}"
                for terminal in table.terminals
                if table.get_action(state, terminal) is not None
            ]
            if entries:
                lines.append(f"State {state}:")
                lines.extend(entries)
        lines.append("")
        lines.append("GOTO")
        for state in range(table.num_states):
            entries = [
                f"  {nt} : {table.get_goto(state, nt)}"
                for nt in table.non_terminals
                if table.get_goto(state, nt) is not None
            ]
            if entries:
                lines.append(f"State {state}:")
                lines.extend(entries)
        return "\n".join(lines)

    def _on_compact_toggled(self, enabled: bool) -> None:
        """Switch between the full grid and the compact listing."""
        self.table.setVisible(not enabled)
        self.compact_text.setVisible(enabled)

    def _apply_search(self) -> None:
        """Hide table rows that do not match the search text."""
        text = self.search.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            if row < len(self._row_text):
                match = text in self._row_text[row]
            else:
                match = False
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is not None and text in item.text().lower():
                        match = True
                        break
            self.table.setRowHidden(row, not match)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Show an explanation for the clicked ACTION/GOTO cell."""
        if self._analysis is None:
            return
        if col == 0 or col == self._divider_col:
            self.detail.clear()
            return
        if col <= len(self._terminals):
            terminal = self._terminals[col - 1]
            self.detail.setPlainText(explain_action(self._analysis, row, terminal))
            return
        index = col - self._goto_start
        if 0 <= index < len(self._non_terminals):
            nt = self._non_terminals[index]
            self.detail.setPlainText(explain_goto(self._analysis, row, nt))