"""Combined Closure Steps + GOTO Steps view.

The per-state closure trace and the per-transition GOTO trace sit side by side,
with the grammar that was actually analysed shown as a third column on the
right.  The two existing views (:class:`~gui.closure_steps_view.ClosureStepsView`
and :class:`~gui.goto_steps_view.GotoStepsView`) are embedded unchanged so their
presentation and logic are reused as-is; this widget only arranges them under
clear section labels and forwards ``clear()`` / ``update_from()``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from gui.closure_steps_view import ClosureStepsView
from gui.goto_steps_view import GotoStepsView
from gui.grammar_reference import GrammarReferencePane

logger = get_logger(__name__)

_SECTION_LABEL_QSS = (
    "font-weight: 600; color: #1E293B; padding: 2px 4px;"
    " border-bottom: 1px solid #E2E8F0;"
)


class ClosureGotoStepsView(QWidget):
    """Closure and GOTO step tables shown side by side, grammar on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.closure = ClosureStepsView()
        self.goto = GotoStepsView()

        # A single shared grammar reference sits to the right of the two tables.
        # Both embedded views keep their own grammar pane internally, so hide
        # those copies to avoid duplication.
        self.grammar = GrammarReferencePane()
        self.closure.grammar.setVisible(False)
        self.goto.grammar.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._section("Closure Steps", self.closure))
        splitter.addWidget(self._section("GOTO Steps", self.goto))
        splitter.addWidget(self._section("Used Grammar", self.grammar))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([420, 420, 360])
        outer.addWidget(splitter, 1)

    @staticmethod
    def _section(title: str, view: QWidget) -> QWidget:
        """Wrap ``view`` under a bold section label."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(title)
        label.setStyleSheet(_SECTION_LABEL_QSS)
        layout.addWidget(label)
        layout.addWidget(view, 1)
        return wrapper

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset both step views and the shared grammar reference."""
        self.closure.clear()
        self.goto.clear()
        self.grammar.clear()

    def update_from(self, analysis) -> None:
        """Populate both step views and the shared grammar reference."""
        self.closure.update_from(analysis)
        self.goto.update_from(analysis)
        self.grammar.set_from_analysis(analysis)