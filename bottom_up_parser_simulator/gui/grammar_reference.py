"""Reusable "used grammar" reference pane for the analysis tabs."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class GrammarReferencePane(QWidget):
    """A small captioned, read-only pane showing the grammar in use.

    The pane is used across the analysis tabs so students can compare the
    displayed FIRST/FOLLOW sets, states, tables, conflicts, etc. with the exact
    (possibly transformed) grammar that produced them.
    """

    def __init__(
        self,
        caption: str = "Used grammar:",
        max_height: int | None = 110,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.caption = QLabel(caption)
        self.caption.setStyleSheet("color: #444;")
        layout.addWidget(self.caption)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        if max_height is not None:
            self.view.setMaximumHeight(max_height)
        self.view.setMinimumWidth(280)
        self.view.setPlaceholderText("The grammar used appears here.")
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.view.setFont(mono)
        layout.addWidget(self.view, 1)

    def set_grammar(self, text: str) -> None:
        """Show ``text`` as the grammar in use."""
        self.view.setPlainText(text)

    def clear(self) -> None:
        """Clear the pane."""
        self.view.clear()