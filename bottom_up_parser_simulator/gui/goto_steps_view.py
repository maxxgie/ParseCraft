"""Step-by-step GOTO computation for a selected transition.

Presented as a table (matching the State Transitions tab) instead of a plain
text dump: rows walk through the origin items, the dot advance over the symbol,
any closure additions and the resulting target state.
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

COLUMNS = ["Phase", "Item", "Dot-Advanced / Added", "Trigger (• symbol)"]

# Column indices.
COL_PHASE = 0
COL_ITEM = 1
COL_ADDED = 2
COL_TRIGGER = 3


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

        self.grammar = GrammarReferencePane()
        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        top_row.addWidget(self.grammar, 0)
        layout.addLayout(top_row)

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
        self.table.setRowCount(0)
        self.grammar.clear()
        self.header.setText("Generate a grammar to see GOTO steps.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the state selector and show the first transition."""
        self._analysis = analysis
        self.grammar.set_from_analysis(analysis)
        self._updating = True
        self.state_combo.blockSignals(True)
        self.state_combo.clear()
        for state in analysis.automaton.states:
            self.state_combo.addItem(f"I{state.state_id}", state.state_id)
        self.state_combo.blockSignals(False)
        self._updating = False
        if self.state_combo.count() > 0:
            # ``addItem`` already moved the current index to 0 while signals
            # were blocked, so setCurrentIndex(0) would be a no-op and no
            # signal would fire. Populate and render the first transition
            # explicitly so the tab is never left blank after Generate.
            self.state_combo.setCurrentIndex(0)
            self._populate_symbols()
            self._render()
        else:
            self.symbol_combo.clear()
            self.table.setRowCount(0)

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
            self.table.setRowCount(0)
            return

        automaton = self._analysis.automaton
        if not hasattr(automaton, "goto_trace"):
            self.table.setRowCount(0)
            self.header.setText(
                "GOTO tracing is not available for this automaton."
            )
            self.header.setStyleSheet("color: #B71C1C;")
            return

        state = automaton.get_state(state_id)
        origin_items = sorted(
            (item for item in state.items if item.next_symbol() == symbol),
            key=_item_key,
        )
        trace = automaton.goto_trace(state_id, symbol)

        rows: list[tuple[str, str, str, str]] = []

        # Items with the dot before the symbol.
        if origin_items:
            for item in origin_items:
                rows.append(("Before", item.to_string(), "", f"• {symbol}"))
        else:
            rows.append(("Before", "(no item has • before this symbol)", "", ""))

        # Dot advanced over the symbol (pre-closure).
        moved = trace.get("moved", [])
        if moved:
            for item in sorted(moved, key=_item_key):
                rows.append(("Dot moved", "", item.to_string(), symbol))
        else:
            rows.append(("Dot moved", "(none)", "", ""))

        # Closure additions.
        closure_steps = trace.get("closure_steps", [])
        step_no = 0
        for step in closure_steps:
            if step.get("kind") != "add":
                continue
            step_no += 1
            origin = step.get("from")
            added = step.get("item")
            rows.append(("Closure add", origin.to_string(), added.to_string(), ""))
        if step_no == 0:
            rows.append(("Closure", "(no closure additions)", "", ""))

        # Resulting state items.
        for item in sorted(trace.get("result", []), key=_item_key):
            rows.append(("Result", item.to_string(), "", ""))

        self.table.setRowCount(len(rows))
        for row_index, (phase, item, added, trigger) in enumerate(rows):
            self.table.setItem(row_index, COL_PHASE, _phase_cell(phase))
            self.table.setItem(row_index, COL_ITEM, _mono_cell(item))
            self.table.setItem(row_index, COL_ADDED, _mono_cell(added))
            self.table.setItem(row_index, COL_TRIGGER, _mono_cell(trigger))

        target = trace.get("target")
        target_text = "none" if target is None else f"I{target}"
        self.header.setText(
            f"GOTO(I{state_id}, {symbol}) → {target_text} "
            f"({len(trace.get('result', []))} items)."
        )
        self.header.setStyleSheet("color: #333;")