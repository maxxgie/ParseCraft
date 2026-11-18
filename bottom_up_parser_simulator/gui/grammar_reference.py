"""Reusable "used grammar" reference pane for the analysis tabs."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.table_builder import LR_PARSER_TYPES
from models.grammar import Grammar


class GrammarReferencePane(QWidget):
    """A small captioned, read-only pane showing the grammar in use.

    The pane is used across the analysis tabs so students can compare the
    displayed FIRST/FOLLOW sets, states, tables, conflicts, etc. with the exact
    (possibly transformed, possibly augmented) grammar that produced them.

    The grammar is always shown in **expanded, textbook form**: one production
    per line, the ``->`` arrow aligned, a blank line between non-terminals, and
    never the ``|`` shorthand.  LR-family parsers show the augmented grammar
    (``S' -> S``); other parsers show the original/transformed grammar.
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
        self._default_caption = caption
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

    def set_caption(self, text: str) -> None:
        """Update the caption label above the grammar text."""
        self.caption.setText(text)

    def set_grammar(self, text: str) -> None:
        """Show ``text`` verbatim as the grammar in use (raw BNF)."""
        self.view.setPlainText(text)

    def set_from_grammar(
        self, grammar: Grammar | None, caption: str = "Grammar Used by Parser"
    ) -> None:
        """Show ``grammar`` in expanded, textbook form.

        Args:
            grammar: The grammar to display (original, transformed, …).
            caption: Label shown above the grammar identifying its version.
        """
        if grammar is None:
            self.view.clear()
            return
        self.set_caption(caption)
        self.view.setPlainText(grammar.to_expanded_text())

    def set_from_analysis(self, analysis) -> None:
        """Show the grammar actually used by ``analysis`` with a version label.

        The caption names the grammar version so the user always knows what is
        being parsed:

        * LR-family parsers (Shift Reduce, LR(0), SLR(1), CLR(1), LALR(1))
          operate on the **augmented** grammar (``S' -> S``) — the caption reads
          *"Augmented Grammar Used by Parser"*.
        * Top-down parsers operate on the **transformed** grammar (after any
          left-recursion removal / left factoring) — the caption reads
          *"Transformed Grammar"* when transforms were applied, otherwise
          *"Grammar Used by Parser"*.
        """
        grammar = getattr(analysis, "grammar", None)
        if grammar is None:
            self.view.clear()
            return
        parser_type = getattr(analysis, "parser_type", None)
        automaton = getattr(analysis, "automaton", None)
        if (
            parser_type in LR_PARSER_TYPES
            and automaton is not None
            and getattr(automaton, "augmented_grammar", None) is not None
        ):
            self.set_caption("Augmented Grammar Used by Parser")
            self.view.setPlainText(automaton.augmented_grammar.to_expanded_text())
            return
        transforms = getattr(analysis, "transforms", None) or []
        self.set_caption(
            "Transformed Grammar" if transforms else "Grammar Used by Parser"
        )
        self.view.setPlainText(grammar.to_expanded_text())

    def clear(self) -> None:
        """Clear the pane and restore the default caption."""
        self.view.clear()
        self.set_caption(self._default_caption)