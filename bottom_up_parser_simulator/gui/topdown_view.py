"""Top-down parsing panel (recursive descent, backtracking, LL(1))."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.ast import AstNode, parse_tree_to_ast
from core.logging_config import get_logger
from core.topdown import TopDownResult, simulate_topdown
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_ACTION_COLORS = {
    "call": "#E3E8FB",
    "match": "#D9EAD3",
    "predict": "#CFE2FF",
    "decision": "#FFF3CD",
    "backtrack": "#F4C7C3",
    "recover": "#F4C7C3",
    "accept": "#93C47D",
    "error": "#F4C7C3",
    "start": "#EEEEEE",
}


def _cell(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    return item


class TopDownView(QWidget):
    """Runs a top-down parser and lets the user step through its trace.

    Signals:
        parse_finished(bool, str): Emitted with ``(accepted, message)``.
        parse_tree_ready(object): Emitted with the parse tree on success.
        ast_ready(object): Emitted with the :class:`AstNode` on success.
    """

    parse_finished = pyqtSignal(bool, str)
    parse_tree_ready = pyqtSignal(object)
    ast_ready = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: Optional[TopDownResult] = None
        self._step_index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.method_label = QLabel("No top-down analysis yet.")
        self.method_label.setWordWrap(True)
        self.method_label.setStyleSheet("color: #333;")

        self.grammar = GrammarReferencePane()
        top_row = QHBoxLayout()
        top_row.addWidget(self.method_label, 1)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Input:"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("e.g. id + id * id")
        self.input_edit.returnPressed.connect(self.run)
        input_row.addWidget(self.input_edit, 1)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run)
        input_row.addWidget(self.run_button)

        self.step_button = QPushButton("Step")
        self.step_button.clicked.connect(self.step_forward)
        input_row.addWidget(self.step_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset)
        input_row.addWidget(self.reset_button)
        layout.addLayout(input_row)

        self.config_label = QLabel("No simulation yet.")
        self.config_label.setWordWrap(True)
        self.config_label.setStyleSheet(
            "background: #F5F5F5; border: 1px solid #CCC; padding: 4px; color: #333;"
        )
        layout.addWidget(self.config_label)

        self.steps_table = QTableWidget(0, 4)
        self.steps_table.setHorizontalHeaderLabels(
            ["#", "Call stack", "Input remaining", "Action"]
        )
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.steps_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.steps_table, 1)

        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    def set_analysis(self, result: Optional[TopDownResult]) -> None:
        """Attach (or clear) the top-down analysis used for simulation."""
        self._result = result
        self._step_index = 0
        self.steps_table.setRowCount(0)
        if result is None:
            self.method_label.setText("No top-down analysis yet.")
            self.grammar.clear()
            self._set_controls_enabled(False)
            return

        notes = []
        if result.left_recursion:
            notes.append("left recursion detected")
        if result.left_factoring:
            notes.append("common prefixes (left factoring advised)")
        if result.conflicts:
            notes.append(f"{len(result.conflicts)} LL(1) conflict(s)")
        note = (" — " + "; ".join(notes)) if notes else " — LL(1) clean"
        self.method_label.setText(
            f"{result.method} for grammar '{result.grammar.start_symbol}'{note}. "
            "Enter an input string and press Run."
        )
        self.grammar.set_from_analysis(result)
        self._set_controls_enabled(True)

    def clear(self) -> None:
        """Reset back to an empty state."""
        self.set_analysis(None)

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Run a full top-down parse over the current input."""
        if self._result is None:
            self.config_label.setText("Generate a grammar first.")
            return
        simulate_topdown(self._result, self.input_edit.text())
        self._step_index = 0

        self.steps_table.setRowCount(len(self._result.steps))
        for row, step in enumerate(self._result.steps):
            cells = [
                str(step.index + 1),
                " : ".join(step.stack),
                " ".join(step.input_remaining),
                step.action_text,
            ]
            for col, text in enumerate(cells):
                self.steps_table.setItem(row, col, _cell(text))

        self._highlight_step(0)
        self._finish()

    def step_forward(self) -> None:
        """Advance the highlighted step by one."""
        if not self._result or not self._result.steps:
            return
        if self._step_index < len(self._result.steps) - 1:
            self._step_index += 1
            self._highlight_step(self._step_index)

    def reset(self) -> None:
        """Return to the first configuration."""
        if not self._result or not self._result.steps:
            return
        self._step_index = 0
        self._highlight_step(0)

    # ------------------------------------------------------------------
    def _finish(self) -> None:
        if self._result is None:
            return
        if self._result.accepted:
            message = f"Accepted in {len(self._result.steps)} steps."
            self.parse_finished.emit(True, message)
            if self._result.parse_tree is not None:
                self.parse_tree_ready.emit(self._result.parse_tree)
                self.ast_ready.emit(parse_tree_to_ast(self._result.parse_tree))
        else:
            message = self._result.error or "Parse failed."
            self.parse_finished.emit(False, message)

    def _highlight_step(self, index: int) -> None:
        if not self._result or not self._result.steps:
            return
        index = max(0, min(index, len(self._result.steps) - 1))
        self._step_index = index
        self.steps_table.selectRow(index)
        item = self.steps_table.item(index, 0)
        if item is not None:
            self.steps_table.scrollToItem(
                item, QTableWidget.ScrollHint.PositionAtCenter
            )
        step = self._result.steps[index]
        color = _ACTION_COLORS.get(step.action, "#FFFFFF")
        self.config_label.setStyleSheet(
            f"background: {color}; border: 1px solid #999; padding: 4px; color: #222;"
        )
        self.config_label.setText(
            f"Step {step.index + 1}/{len(self._result.steps)}  •  {step.action_text}"
        )

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)
        self.step_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)