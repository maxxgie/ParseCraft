"""ACTION / GOTO parsing-table display."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from core.logging_config import get_logger
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


class TableView(QWidget):
    """Tabbed ACTION and GOTO tables with conflict reporting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see ACTION/GOTO tables.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        self._show_errors = False

        self.tabs = QTabWidget()

        self.action_table = QTableWidget(0, 0)
        self.action_table.verticalHeader().setVisible(True)
        self.action_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.action_table.setAlternatingRowColors(False)
        self.tabs.addTab(self.action_table, "ACTION")

        self.goto_table = QTableWidget(0, 0)
        self.goto_table.verticalHeader().setVisible(True)
        self.goto_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.goto_table, "GOTO")

        layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the tables."""
        self.action_table.clear()
        self.action_table.setRowCount(0)
        self.action_table.setColumnCount(0)
        self.goto_table.clear()
        self.goto_table.setRowCount(0)
        self.goto_table.setColumnCount(0)
        self.header.setText("Generate a grammar to see ACTION/GOTO tables.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis, show_errors: bool = False) -> None:
        """Fill the tables from an analysis result.

        Args:
            analysis: The analysis to display.
            show_errors: When ``True``, empty ACTION cells read ``Error``
                instead of being left blank.
        """
        self._show_errors = show_errors
        table = analysis.table
        self._fill_action(table)
        self._fill_goto(table)

        conflicts = analysis.conflicts
        resolutions = analysis.resolutions
        if conflicts:
            resolved_count = len(resolutions)
            unresolved = len(analysis.unresolved_conflicts)
            preview = "\n".join(c.message for c in conflicts[:6])
            more = "" if len(conflicts) <= 6 else f"\n... (+{len(conflicts) - 6} more)"
            self.header.setText(
                f"⚠ {analysis.parser_type} table: {len(conflicts)} conflict(s), "
                f"{resolved_count} resolved, {unresolved} unresolved.\n"
                f"{preview}{more}"
            )
            self.header.setStyleSheet(
                "color: #B00020;" if unresolved else "color: #8A6D00;"
            )
        else:
            self.header.setText(
                f"{analysis.parser_type}: conflict-free table with "
                f"{table.num_states} states. "
                "Legend: ACTION — blue = shift, green = reduce, "
                "dark green (bold) = accept, red = error; "
                "GOTO — lavender = state transition."
            )
            self.header.setStyleSheet("color: #1E6B34;")

    def _prepare(self, table_widget: QTableWidget, columns: list[str], rows: int) -> None:
        table_widget.clear()
        table_widget.setColumnCount(len(columns) + 1)
        table_widget.setRowCount(rows)
        headers = ["State"] + columns
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setVerticalHeaderLabels([str(i) for i in range(rows)])
        table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table_widget.verticalHeader().setDefaultSectionSize(22)

    def _fill_action(self, table) -> None:
        terminals = table.terminals
        self._prepare(self.action_table, terminals, table.num_states)
        for state in range(table.num_states):
            self.action_table.setItem(state, 0, _cell(str(state)))
            for col, terminal in enumerate(terminals, start=1):
                action = table.get_action(state, terminal)
                if action is None:
                    if self._show_errors:
                        cell = _cell("Error", ERROR_BG, ERROR_FG)
                    else:
                        cell = _cell("", BLANK_BG, BLANK_FG)
                else:
                    bg, fg = action_colors(action.action_type)
                    cell = _cell(
                        action.to_string(),
                        bg,
                        fg,
                        bold=action.action_type == "accept",
                    )
                self.action_table.setItem(state, col, cell)

    def _fill_goto(self, table) -> None:
        non_terminals = table.non_terminals
        self._prepare(self.goto_table, non_terminals, table.num_states)
        for state in range(table.num_states):
            self.goto_table.setItem(state, 0, _cell(str(state)))
            for col, nt in enumerate(non_terminals, start=1):
                target = table.get_goto(state, nt)
                if target is not None:
                    cell = _cell(str(target), GOTO_BG, GOTO_FG, bold=True)
                else:
                    cell = _cell("", BLANK_BG, BLANK_FG)
                self.goto_table.setItem(state, col, cell)