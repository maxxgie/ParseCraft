"""Step-by-step closure computation for a selected LR state.

Presented as a table (matching the State Transitions tab) instead of a plain
text dump: each row is one closure step, so the kernel, every ``A -> α • B β``
⇒ ``B -> • γ`` addition and the final item set line up in columns.
"""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

COLUMNS = ["Phase", "Origin Item", "Added Item", "Trigger (• symbol)"]

# Column indices.
COL_PHASE = 0
COL_ORIGIN = 1
COL_ADDED = 2
COL_TRIGGER = 3

PHASE_BG = "#1E293B"
PHASE_FG = "#F8FAFC"


def _item_key(item):
    return (item.lhs, item.rhs, item.dot, item.lookahead)


def _mono_cell(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    item.setFont(font)
    return item


def _phase_cell(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(True)
    item.setFont(font)
    return item


class ClosureStepsView(QWidget):
    """Shows how a state's closure is built from its kernel items."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see closure steps.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")

        self.grammar = GrammarReferencePane()
        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

        row = QHBoxLayout()
        row.addWidget(QLabel("State:"))
        self.state_combo = QComboBox()
        self.state_combo.currentIndexChanged.connect(self._render)
        row.addWidget(self.state_combo, 1)
        layout.addLayout(row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self._analysis = None

    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        self.state_combo.blockSignals(False)
        self.table.setRowCount(0)
        self.grammar.clear()
        self.header.setText("Generate a grammar to see closure steps.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the state selector and show the first state's closure."""
        self._analysis = analysis
        automaton = analysis.automaton
        self.grammar.set_from_analysis(analysis)
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        for state in automaton.states:
            self.state_combo.addItem(f"I{state.state_id}", state.state_id)
        self.state_combo.blockSignals(False)
        if self.state_combo.count() > 0:
            self.state_combo.setCurrentIndex(0)
        self._render()

    def _render(self) -> None:
        if self._analysis is None:
            return
        state_id = self.state_combo.currentData()
        if state_id is None:
            self.table.setRowCount(0)
            return
        automaton = self._analysis.automaton
        if not hasattr(automaton, "closure_trace"):
            self.table.setRowCount(0)
            self.header.setText(
                "Closure tracing is not available for this automaton."
            )
            self.header.setStyleSheet("color: #B71C1C;")
            return

        trace = automaton.closure_trace(state_id)

        rows: list[tuple[str, str, str, str]] = []

        # Kernel (seed items).
        kernel = sorted(trace.get("kernel", []), key=_item_key)
        if kernel:
            for item in kernel:
                rows.append(("Kernel", item.to_string(), "", ""))
        else:
            rows.append(("Kernel", "(empty)", "", ""))

        # Closure additions: A -> α • B β  ⇒  add B -> • γ.
        step_no = 0
        for step in trace.get("steps", []):
            if step.get("kind") != "add":
                continue
            step_no += 1
            origin = step.get("from")
            added = step.get("item")
            symbol = step.get("symbol")
            rows.append(
                (
                    f"Step {step_no}",
                    origin.to_string(),
                    added.to_string(),
                    f"• {symbol}",
                )
            )
        if step_no == 0:
            rows.append(("Step", "(none — kernel already closed)", "", ""))

        # Final closure items.
        for item in sorted(trace.get("result", []), key=_item_key):
            rows.append(("Final", item.to_string(), "", ""))

        self.table.setRowCount(len(rows))
        for row_index, (phase, origin, added, trigger) in enumerate(rows):
            self.table.setItem(row_index, COL_PHASE, _phase_cell(phase))
            self.table.setItem(row_index, COL_ORIGIN, _mono_cell(origin))
            self.table.setItem(row_index, COL_ADDED, _mono_cell(added))
            self.table.setItem(row_index, COL_TRIGGER, _mono_cell(trigger))

        matches = "yes" if trace.get("matches") else "NO — state is inconsistent"
        self.header.setText(
            f"Closure for I{state_id}: {len(trace.get('result', []))} items, "
            f"{step_no} addition(s). Recomputed closure equals stored state: "
            f"{matches}."
        )
        self.header.setStyleSheet("color: #333;")