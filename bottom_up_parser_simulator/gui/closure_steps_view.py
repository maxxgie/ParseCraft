"""Step-by-step closure computation for a selected LR state."""

from __future__ import annotations

from typing import List

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger

logger = get_logger(__name__)


def _item_key(item):
    return (item.lhs, item.rhs, item.dot, item.lookahead)


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
        layout.addWidget(self.header)

        row = QHBoxLayout()
        row.addWidget(QLabel("State:"))
        self.state_combo = QComboBox()
        self.state_combo.currentIndexChanged.connect(self._render)
        row.addWidget(self.state_combo, 1)
        layout.addLayout(row)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text, 1)

        self._analysis = None

    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        self.state_combo.blockSignals(False)
        self.text.clear()
        self.header.setText("Generate a grammar to see closure steps.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the state selector and show the first state's closure."""
        self._analysis = analysis
        automaton = analysis.automaton
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
            self.text.clear()
            return
        automaton = self._analysis.automaton
        if not hasattr(automaton, "closure_trace"):
            self.text.setPlainText("Closure tracing is not available for this automaton.")
            return

        trace = automaton.closure_trace(state_id)
        lines: List[str] = [
            f"Closure of State I{state_id}",
            "=" * 60,
            "",
            "Kernel (seed items):",
            "",
        ]
        kernel = sorted(trace.get("kernel", []), key=_item_key)
        if kernel:
            for item in kernel:
                lines.append("  " + item.to_string())
        else:
            lines.append("  (empty)")

        lines.append("")
        lines.append("Closure steps (add B -> •γ for A -> α • B β):")
        lines.append("")
        step_no = 0
        for step in trace.get("steps", []):
            if step.get("kind") != "add":
                continue
            step_no += 1
            origin = step.get("from")
            added = step.get("item")
            symbol = step.get("symbol")
            lines.append(
                f"  {step_no}. {origin.to_string()}   ⇒   add {added.to_string()}"
                f"   [because • {symbol}]"
            )
        if step_no == 0:
            lines.append("  (no new items — the kernel is already closed)")

        lines.append("")
        lines.append("Final closure items:")
        lines.append("")
        for item in sorted(trace.get("result", []), key=_item_key):
            lines.append("  " + item.to_string())

        lines.append("")
        matches = "yes" if trace.get("matches") else "NO — state is inconsistent"
        lines.append(f"Recomputed closure equals stored state: {matches}")

        self.text.setPlainText("\n".join(lines))
        self.header.setText(
            f"Closure for I{state_id}: {len(trace.get('result', []))} items, "
            f"{step_no} addition(s)."
        )
        self.header.setStyleSheet("color: #333;")