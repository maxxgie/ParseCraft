"""Generated-parser code viewer: line numbers, Python highlighting, actions.

The tab presents the generated, runnable LR parser in a lightweight code
editor that matches the rest of the app: a fixed monospace font, a line-number
gutter, Python syntax highlighting, current-line emphasis, and Copy / Select
All / Save actions.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger

logger = get_logger(__name__)

# --- palette (aligned with gui/theme.py) -----------------------------------
GUTTER_BG = QColor("#F1F5F9")
GUTTER_FG = QColor("#94A3B8")
CURRENT_LINE_BG = QColor("#F8FAFC")

KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
}
BUILTINS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "getattr", "int",
    "len", "list", "max", "min", "print", "range", "repr", "reversed", "set",
    "sorted", "str", "sum", "tuple", "type", "zip", "isinstance", "Exception",
}

_KEYWORD_FMT = QTextCharFormat()
_KEYWORD_FMT.setForeground(QColor("#7C3AED"))
_KEYWORD_FMT.setFontWeight(QFont.Weight.Bold)

_BUILTIN_FMT = QTextCharFormat()
_BUILTIN_FMT.setForeground(QColor("#0F766E"))

_STRING_FMT = QTextCharFormat()
_STRING_FMT.setForeground(QColor("#0F766E"))

_COMMENT_FMT = QTextCharFormat()
_COMMENT_FMT.setForeground(QColor("#6B7280"))
_COMMENT_FMT.setFontItalic(True)

_NUMBER_FMT = QTextCharFormat()
_NUMBER_FMT.setForeground(QColor("#B45309"))

_DEFNAME_FMT = QTextCharFormat()
_DEFNAME_FMT.setForeground(QColor("#1E3A8A"))
_DEFNAME_FMT.setFontWeight(QFont.Weight.Bold)

_DECORATOR_FMT = QTextCharFormat()
_DECORATOR_FMT.setForeground(QColor("#C2410C"))


class PythonHighlighter(QSyntaxHighlighter):
    """A compact Python syntax highlighter (keywords, strings, comments, …).

    Matching uses the standard-library :mod:`re` module rather than
    ``QRegularExpression``: on some Qt builds, formatting a range derived from
    a ``QRegularExpressionMatch`` while highlighting crashes the (offscreen)
    paint backend, whereas plain-Python match objects are always safe.
    """

    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules: List[Tuple[re.Pattern, QTextCharFormat]] = []
        for word in KEYWORDS:
            self._rules.append((re.compile(rf"\b{word}\b"), _KEYWORD_FMT))
        for word in BUILTINS:
            self._rules.append((re.compile(rf"\b{word}\b"), _BUILTIN_FMT))
        self._rules.append((re.compile(r"\b\d+(\.\d+)?\b"), _NUMBER_FMT))
        self._rules.append((re.compile(r"\bdef\s+(\w+)"), _DEFNAME_FMT))
        self._rules.append((re.compile(r"\bclass\s+(\w+)"), _DEFNAME_FMT))
        self._rules.append((re.compile(r"^\s*@\w+"), _DECORATOR_FMT))

        self._string_re = re.compile(r"'([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"")
        self._comment_re = re.compile(r"#[^\n]*")

    # ------------------------------------------------------------------
    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt naming)
        state = self.previousBlockState()

        # Continuation of a multi-line (triple-quoted) string.
        if state in (1, 2):
            delim = "'''" if state == 1 else '"""'
            close = text.find(delim)
            if close == -1:
                self.setFormat(0, len(text), _STRING_FMT)
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, close + 3, _STRING_FMT)
            self._apply_rules(text, start=close + 3)
            self.setCurrentBlockState(0)
            return

        # A triple-quote opener on this line?
        opener = self._find_triple_opener(text)
        if opener is not None:
            idx, delim, next_state = opener
            close = text.find(delim, idx + 3)
            self._apply_rules(text, start=0, end=idx)
            if close == -1:
                self.setFormat(idx, len(text) - idx, _STRING_FMT)
                self.setCurrentBlockState(next_state)
            else:
                self.setFormat(idx, close + 3 - idx, _STRING_FMT)
                self._apply_rules(text, start=close + 3)
                self.setCurrentBlockState(0)
            return

        self._apply_rules(text, start=0)
        self.setCurrentBlockState(0)

    @staticmethod
    def _find_triple_opener(text: str) -> Optional[Tuple[int, str, int]]:
        best: Optional[Tuple[int, str, int]] = None
        for delim, next_state in (("'''", 1), ('"""', 2)):
            idx = text.find(delim)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, delim, next_state)
        return best

    def _apply_rules(self, text: str, start: int = 0, end: Optional[int] = None) -> None:
        if end is None:
            end = len(text)

        comment_start = -1
        cm = self._comment_re.search(text)
        if cm is not None and start <= cm.start() < end:
            s = max(cm.start(), start)
            e = min(cm.end(), end)
            self.setFormat(s, e - s, _COMMENT_FMT)
            comment_start = cm.start()

        def apply(pattern: re.Pattern, fmt: QTextCharFormat) -> None:
            for match in pattern.finditer(text):
                s = match.start()
                if s < start or s >= end:
                    continue
                if comment_start != -1 and s >= comment_start:
                    continue
                self.setFormat(s, match.end() - match.start(), fmt)

        apply(self._string_re, _STRING_FMT)
        for pattern, fmt in self._rules:
            apply(pattern, fmt)


class _LineArea(QWidget):
    """The left gutter that paints line numbers."""

    def __init__(self, editor: "_CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.editor.line_number_area_paint_event(event)


class _CodeEditor(QPlainTextEdit):
    """Read-only editor with a line-number gutter and current-line band."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.line_area = _LineArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_line_numbers)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFont("Consolas", 10))
        self.setMinimumSize(200, 200)
        self._update_margin(0)
        self._highlight_current_line()

    # -- geometry -----------------------------------------------------
    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, _new_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_numbers(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin(0)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    # -- painting -----------------------------------------------------
    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), GUTTER_BG)
        painter.setPen(GUTTER_FG)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self.line_area.width() - 8,
                    height,
                    int(Qt.AlignmentFlag.AlignRight),
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(CURRENT_LINE_BG)
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])


class CodeView(QWidget):
    """Syntax-highlighted generated-parser viewer with Copy / Save actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see the generated parser.")
        self.header.setStyleSheet("color: #555;")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy the generated source to the clipboard")
        self.copy_button.clicked.connect(self._on_copy)
        buttons.addWidget(self.copy_button)

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self._on_select_all)
        buttons.addWidget(self.select_all_button)

        buttons.addStretch(1)
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Save the generated parser as a .py file")
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

        self.editor = _CodeEditor()
        self.highlighter = PythonHighlighter(self.editor.document())
        layout.addWidget(self.editor, 1)

        self._code = ""
        self._set_buttons_enabled(False)

    # ------------------------------------------------------------------
    def set_code(self, code: str, note: str = "") -> None:
        """Display the generated code."""
        self._code = code
        self.editor.setPlainText(code)
        self.header.setText(note or "Generated parser (runnable Python).")
        self.header.setStyleSheet("color: #1E6B34;")
        self._set_buttons_enabled(True)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)

    def clear(self) -> None:
        """Reset the view."""
        self._code = ""
        self.editor.clear()
        self.header.setText("Generate a grammar to see the generated parser.")
        self.header.setStyleSheet("color: #555;")
        self._set_buttons_enabled(False)

    # ------------------------------------------------------------------
    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.save_button.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)
        self.select_all_button.setEnabled(enabled)

    def _on_copy(self) -> None:
        if self._code:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self._code)

    def _on_select_all(self) -> None:
        self.editor.selectAll()

    def _on_save(self) -> None:
        if not self._code:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Generated Parser", "parser.py", "Python Files (*.py)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._code)
            self.header.setText(f"Saved to {path}")
        except OSError as exc:  # pragma: no cover - filesystem dependent
            logger.error("Failed to save generated parser: %s", exc)
            self.header.setText(f"Failed to save: {exc}")