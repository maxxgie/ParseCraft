"""Step-by-step parsing simulation panel."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
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

from core.error_recovery import RECOVERY_MODES, recover_input
from core.logging_config import get_logger
from core.parser_simulator import SimulationResult, simulate
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)


def _cell(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    return item


class SimulationView(QWidget):
    """Runs the LR parser and lets the user step through configurations.

    Signals:
        parse_tree_ready(object): Emitted with the :class:`ParseTreeNode` when
            the input is accepted.
        simulation_finished(bool, str): Emitted with ``(accepted, message)``.
    """

    parse_tree_ready = pyqtSignal(object)
    simulation_finished = pyqtSignal(bool, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analysis = None
        self._result: Optional[SimulationResult] = None
        self._step_index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

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

        recovery_row = QHBoxLayout()
        recovery_row.addWidget(QLabel("Error recovery:"))
        self.recovery_combo = QComboBox()
        self.recovery_combo.addItem("None", None)
        for mode in RECOVERY_MODES:
            self.recovery_combo.addItem(mode, mode)
        recovery_row.addWidget(self.recovery_combo)
        recovery_row.addStretch(1)
        layout.addLayout(recovery_row)

        self.recovery_label = QLabel("")
        self.recovery_label.setWordWrap(True)
        self.recovery_label.setStyleSheet(
            "background: #FFF8E1; border: 1px solid #E0C97F; padding: 4px; color: #5A4300;"
        )
        self.recovery_label.setVisible(False)
        layout.addWidget(self.recovery_label)

        self.config_label = QLabel("No simulation yet.")
        self.config_label.setWordWrap(True)
        self.config_label.setStyleSheet(
            "background: #F5F5F5; border: 1px solid #CCC; padding: 4px; color: #333;"
        )
        layout.addWidget(self.config_label)

        self.steps_table = QTableWidget(0, 5)
        self.steps_table.setHorizontalHeaderLabels(
            ["#", "Stack (state:symbol)", "Input remaining", "Action", "Rule"]
        )
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.steps_table, 1)

        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_analysis(self, analysis) -> None:
        """Attach (or clear) the analysis used for simulation."""
        self._analysis = analysis
        self._result = None
        self._step_index = 0
        self.steps_table.setRowCount(0)
        if analysis is None:
            self.config_label.setText("Generate a grammar first.")
            self._set_controls_enabled(False)
        else:
            self.config_label.setText(
                f"Ready to simulate with {analysis.parser_type}. "
                "Enter an input string and press Run."
            )
            self._set_controls_enabled(True)

    def clear(self) -> None:
        """Reset everything back to an empty state."""
        self.set_analysis(None)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Run a full simulation over the current input."""
        if self._analysis is None:
            self.config_label.setText("Generate a grammar before simulating.")
            return

        input_string = self.input_edit.text()
        recovery_mode = self.recovery_combo.currentData()
        if recovery_mode is not None:
            self._run_recovery(input_string, recovery_mode)
            return

        self.recovery_label.setVisible(False)
        self._result = simulate(self._analysis.table, self._analysis.grammar, input_string)
        self._step_index = 0
        self._fill_steps(self._result.steps)
        self._highlight_step(0)
        self._finish()

    def _run_recovery(self, input_string: str, mode: str) -> None:
        report = recover_input(
            self._analysis.table, self._analysis.grammar, input_string, mode
        )
        self._result = report
        self._step_index = 0
        self._fill_steps(report.steps)
        self._highlight_step(0)
        self.recovery_label.setVisible(True)
        self.recovery_label.setText(report.report_text())
        if report.accepted:
            message = (
                f"Accepted after recovery ({len(report.events)} action(s))."
            )
            self.simulation_finished.emit(True, message)
            if report.parse_tree is not None:
                self.parse_tree_ready.emit(report.parse_tree)
        else:
            message = report.error or "Parse failed after recovery."
            self.simulation_finished.emit(False, message)

    def _fill_steps(self, steps) -> None:
        self.steps_table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            rule_text = step.rule_text or (
                f"R{step.rule_number}" if step.rule_number is not None else ""
            )
            cells = [
                str(step.index + 1),
                step.stack_string(),
                " ".join(step.input_remaining),
                step.action_text,
                rule_text,
            ]
            for col, text in enumerate(cells):
                self.steps_table.setItem(row, col, _cell(text))

    def step_forward(self) -> None:
        """Advance the highlighted step by one."""
        if self._result is None:
            return
        if self._step_index < len(self._result.steps) - 1:
            self._step_index += 1
            self._highlight_step(self._step_index)
            self._update_config_label()

    def reset(self) -> None:
        """Return to the first configuration."""
        if self._result is None:
            return
        self._step_index = 0
        self._highlight_step(0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _finish(self) -> None:
        if self._result is None:
            return
        accepted = self._result.accepted
        if accepted:
            message = f"Accepted in {len(self._result.steps)} steps."
            self.simulation_finished.emit(True, message)
            if self._result.parse_tree is not None:
                self.parse_tree_ready.emit(self._result.parse_tree)
        else:
            message = self._result.error or "Parse failed."
            self.simulation_finished.emit(False, message)

    def _highlight_step(self, index: int) -> None:
        if self._result is None or not self._result.steps:
            return
        index = max(0, min(index, len(self._result.steps) - 1))
        self._step_index = index
        self.steps_table.selectRow(index)
        item = self.steps_table.item(index, 0)
        if item is not None:
            self.steps_table.scrollToItem(
                item, QTableWidget.ScrollHint.PositionAtCenter
            )
        self._update_config_label()

    def _update_config_label(self) -> None:
        if self._result is None or not self._result.steps:
            return
        step = self._result.steps[self._step_index]
        color = {
            "shift": "#CFE2FF",
            "reduce": "#D9EAD3",
            "accept": "#93C47D",
            "error": "#F4C7C3",
            "start": "#EEEEEE",
        }.get(step.action, "#FFFFFF")
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