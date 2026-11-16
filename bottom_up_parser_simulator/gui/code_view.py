"""Generated-parser code viewer with copy/save actions."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger

logger = get_logger(__name__)


class CodeView(QWidget):
    """Read-only code viewer with Copy and Save buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see the generated parser.")
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_button = QPushButton("Save...")
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(self.save_button)
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self._on_copy)
        buttons.addWidget(self.copy_button)
        layout.addLayout(buttons)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("Consolas", 9))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
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

    def _on_copy(self) -> None:
        if self._code:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self._code)

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