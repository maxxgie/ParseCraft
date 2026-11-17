"""Combined LR Items + State Transitions view.

The LR-item listing and the state-transition table sit side by side, with the
grammar that was actually analysed shown as a third column on the right.  The
two existing views (:class:`~gui.lr_items_view.LRItemsView` and
:class:`~gui.transition_table_view.TransitionTableView`) are embedded unchanged
so their presentation and logic are reused as-is; this widget only arranges
them under clear section labels and forwards ``clear()`` / ``update_from()``.
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
from gui.grammar_reference import GrammarReferencePane
from gui.lr_items_view import LRItemsView
from gui.transition_table_view import TransitionTableView

logger = get_logger(__name__)

_SECTION_LABEL_QSS = (
    "font-weight: 600; color: #1E293B; padding: 2px 4px;"
    " border-bottom: 1px solid #E2E8F0;"
)


class LRItemsTransitionsView(QWidget):
    """LR items and state-transition tables shown side by side."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lr_items = LRItemsView()
        self.transitions = TransitionTableView()

        # A single shared grammar reference sits above the two tables.  Both
        # embedded views keep their own grammar pane internally, so hide those
        # copies; otherwise the LR Items table would be pushed below the
        # transitions table and the two would not line up side by side.
        self.grammar = GrammarReferencePane()
        self.lr_items.grammar.setVisible(False)
        self.transitions.grammar.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._section("LR Items", self.lr_items))
        splitter.addWidget(self._section("State Transitions", self.transitions))
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
        """Reset both tables and the shared grammar reference."""
        self.lr_items.clear()
        self.transitions.clear()
        self.grammar.clear()

    def update_from(self, analysis) -> None:
        """Populate both tables and the shared grammar reference."""
        self.lr_items.update_from(analysis)
        self.transitions.update_from(analysis)
        self.grammar.set_grammar(analysis.grammar_text)