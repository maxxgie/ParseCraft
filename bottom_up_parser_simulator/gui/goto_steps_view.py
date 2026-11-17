"""Step-by-step GOTO computation for a selected transition."""

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


class GotoStepsView(QWidget):
    """Shows how GOTO(I, X) advances the dot and applies closure."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see GOTO steps.")
        self.header.setWordWrap(True)
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        row = QHBoxLayout()
        row.addWidget(QLabel("State:"))
        self.state_combo = QComboBox()
        row.addWidget(self.state_combo, 1)
        row.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        row.addWidget(self.symbol_combo, 1)
        layout.addLayout(row)

        self.state_combo.currentIndexChanged.connect(self._on_state_changed)
        self.symbol_combo.currentIndexChanged.connect(self._render)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text, 1)

        self._analysis = None
        self._updating = False

    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self._updating = True
        self.state_combo.blockSignals(True)
        self.symbol_combo.blockSignals(True)
        self.state_combo.clear()
        self.symbol_combo.clear()
        self.state_combo.blockSignals(False)
        self.symbol_combo.blockSignals(False)
        self._updating = False
        self.text.clear()
        self.header.setText("Generate a grammar to see GOTO steps.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the state selector and show the first transition."""
        self._analysis = analysis
        self._updating = True
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        for state in analysis.automaton.states:
            self.state_combo.addItem(f"I{state.state_id}", state.state_id)
        self.state_combo.blockSignals(False)
        self._updating = False
        if self.state_combo.count() > 0:
            self.state_combo.setCurrentIndex(0)
        else:
            self.text.clear()

    def _on_state_changed(self) -> None:
        if self._updating or self._analysis is None:
            return
        self._populate_symbols()
        self._render()

    def _populate_symbols(self) -> None:
        state_id = self.state_combo.currentData()
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        if state_id is not None and self._analysis is not None:
            state = self._analysis.automaton.get_state(state_id)
            for symbol in state.transitions:
                self.symbol_combo.addItem(symbol, symbol)
        self.symbol_combo.blockSignals(False)

    def _render(self) -> None:
        if self._analysis is None:
            return
        state_id = self.state_combo.currentData()
        symbol = self.symbol_combo.currentData()
        if state_id is None or symbol is None:
            self.text.clear()
            return

        automaton = self._analysis.automaton
        if not hasattr(automaton, "goto_trace"):
            self.text.setPlainText("GOTO tracing is not available for this automaton.")
            return

        state = automaton.get_state(state_id)
        origin_items = sorted(
            (item for item in state.items if item.next_symbol() == symbol),
            key=_item_key,
        )
        trace = automaton.goto_trace(state_id, symbol)

        lines: List[str] = [
            f"GOTO(I{state_id}, {symbol})",
            "=" * 60,
            "",
            f"Items with the dot before '{symbol}':",
            "",
        ]
        for item in origin_items:
            lines.append("  " + item.to_string())
        if not origin_items:
            lines.append("  (none)")

        lines.append("")
        lines.append("Move the dot over the symbol (before closure):")
        lines.append("")
        moved = trace.get("moved", [])
        for item in sorted(moved, key=_item_key):
            lines.append("  " + item.to_string())
        if not moved:
            lines.append("  (no item has the dot before this symbol)")

        lines.append("")
        lines.append("Closure steps:")
        lines.append("")
        closure_steps = trace.get("closure_steps", [])
        step_no = 0
        for step in closure_steps:
            if step.get("kind") != "add":
                continue
            step_no += 1
            origin = step.get("from")
            added = step.get("item")
            lines.append(
                f"  {step_no}. {origin.to_string()}   ⇒   add {added.to_string()}"
            )
        if step_no == 0:
            lines.append("  (no closure additions)")

        lines.append("")
        target = trace.get("target")
        if target is None:
            lines.append("Target state: (none)")
        else:
            lines.append(f"Target state: I{target}")

        lines.append("")
        lines.append("Resulting state items:")
        lines.append("")
        for item in sorted(trace.get("result", []), key=_item_key):
            lines.append("  " + item.to_string())

        self.text.setPlainText("\n".join(lines))
        target_text = "none" if target is None else f"I{target}"
        self.header.setText(
            f"GOTO(I{state_id}, {symbol}) → {target_text} "
            f"({len(trace.get('result', []))} items)."
        )
        self.header.setStyleSheet("color: #333;")