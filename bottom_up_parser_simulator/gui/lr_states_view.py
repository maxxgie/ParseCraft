"""LR state / item set inspector."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from core.logging_config import get_logger

logger = get_logger(__name__)


class LRStatesView(QWidget):
    """Left-hand list of states plus a right-hand detail pane."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see LR states.")
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.state_list = QListWidget()
        self.state_list.currentRowChanged.connect(self._on_selection)
        splitter.addWidget(self.state_list)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        splitter.addWidget(self.detail)

        splitter.setSizes([180, 520])
        layout.addWidget(splitter, 1)

        self._analysis = None

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self.state_list.clear()
        self.detail.clear()
        self.header.setText("Generate a grammar to see LR states.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the list of states from an analysis result."""
        self._analysis = analysis
        automaton = analysis.automaton
        self.state_list.blockSignals(True)
        self.state_list.clear()
        for state in automaton.states:
            item = QListWidgetItem(f"State {state.state_id}")
            self.state_list.addItem(item)
        self.state_list.blockSignals(False)

        self.header.setText(
            f"{analysis.parser_type}: {len(automaton.states)} states "
            f"({len(automaton.transitions)} transitions)"
            + ("  ⚠ merged (LALR)" if getattr(automaton, "merged", False) else "")
        )
        self.header.setStyleSheet("color: #333;")

        if self.state_list.count() > 0:
            self.state_list.setCurrentRow(0)
        self._show_state(0)

    # ------------------------------------------------------------------
    def _on_selection(self, row: int) -> None:
        if row >= 0:
            self._show_state(row)

    def _show_state(self, state_id: int) -> None:
        if self._analysis is None:
            return
        state = self._analysis.automaton.get_state(state_id)
        lines = [f"State {state_id}", "=" * 40, "", "Items:", ""]
        lines.append(state.get_items_string())
        lines.append("")
        if state.transitions:
            lines.append("Transitions:")
            for symbol, target in sorted(state.transitions.items()):
                lines.append(f"  on '{symbol}'  ->  State {target}")
        else:
            lines.append("Transitions: (none)")
        self.detail.setPlainText("\n".join(lines))