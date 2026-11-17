"""Grammar input editor with parser-type selection and grammar transforms."""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.conflict_resolution import (
    FIRST,
    NONE,
    PRECEDENCE,
    REDUCE,
    REDUCE_REDUCE_OPTIONS,
    SHIFT,
    SHIFT_REDUCE_OPTIONS,
    ResolutionConfig,
)
from core.engine import ALL_PARSER_TYPES
from core.logging_config import get_logger
from core.topdown import TOPDOWN_METHODS

logger = get_logger(__name__)

EXAMPLE_GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"

# Human-readable labels for the strategy combo boxes.
_SHIFT_REDUCE_LABELS = {
    NONE: "None (report)",
    SHIFT: "Prefer Shift",
    REDUCE: "Prefer Reduce",
    PRECEDENCE: "Use Precedence",
}
_REDUCE_REDUCE_LABELS = {
    NONE: "None (report)",
    FIRST: "First Rule",
    PRECEDENCE: "Use Precedence",
}


@dataclass
class GenerateOptions:
    """All user choices needed to run an analysis.

    Attributes:
        parser_type: The selected parser type.
        remove_left_recursion: Whether to remove left recursion.
        left_factoring: Whether to apply left factoring.
        remove_epsilon: Whether to eliminate ε-productions.
        remove_unit: Whether to eliminate unit productions.
        remove_useless: Whether to eliminate unreachable/non-generating symbols.
        resolution: Conflict-resolution configuration.
    """

    parser_type: str
    remove_left_recursion: bool = False
    left_factoring: bool = False
    remove_epsilon: bool = False
    remove_unit: bool = False
    remove_useless: bool = False
    resolution: ResolutionConfig = field(default_factory=ResolutionConfig)
    show_error_cells: bool = False


class GrammarEditor(QWidget):
    """Grammar text box, parser-type selector, transform toggles, conflict
    resolution controls, and a preview of the grammar that is analysed.

    Signals:
        generate_requested(str, object): Emitted with ``(grammar_text,
            options)`` where ``options`` is a :class:`GenerateOptions`.
    """

    generate_requested = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: parser type + generate.
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Parser:"))
        self.parser_combo = QComboBox()
        self.parser_combo.addItems(ALL_PARSER_TYPES)
        self.parser_combo.addItems(TOPDOWN_METHODS)
        self.parser_combo.setCurrentText("SLR(1)")
        row1.addWidget(self.parser_combo, 1)
        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self._on_generate)
        row1.addWidget(self.generate_button)
        layout.addLayout(row1)

        # Row 2: grammar transformations.
        row2 = QHBoxLayout()
        self.remove_left_recursion_cb = self._make_transform_checkbox(
            "Remove Left Recursion",
            "Rewrite A -> A α | β into A -> β A', A' -> α A' | ε "
            "(also removes indirect left recursion).",
        )
        self.left_factoring_cb = self._make_transform_checkbox(
            "Left Factoring",
            "Extract common prefixes: A -> α β1 | α β2 becomes A -> α A', A' -> β1 | β2.",
        )
        self.remove_epsilon_cb = self._make_transform_checkbox(
            "Remove ε",
            "Eliminate A -> ε productions while preserving the language.",
        )
        self.remove_unit_cb = self._make_transform_checkbox(
            "Remove Unit",
            "Eliminate unit productions A -> B (single non-terminal body).",
        )
        self.remove_useless_cb = self._make_transform_checkbox(
            "Remove Useless",
            "Eliminate unreachable and non-generating non-terminals.",
        )
        for checkbox in (
            self.remove_left_recursion_cb,
            self.left_factoring_cb,
            self.remove_epsilon_cb,
            self.remove_unit_cb,
            self.remove_useless_cb,
        ):
            row2.addWidget(checkbox)
        row2.addStretch(1)
        layout.addLayout(row2)

        # Row 3: conflict resolution.
        row3 = QHBoxLayout()
        self.resolve_cb = QCheckBox("Resolve Conflicts")
        self.resolve_cb.setToolTip(
            "Resolve shift/reduce and reduce/reduce conflicts after building "
            "the table, instead of leaving them reported."
        )
        self.resolve_cb.toggled.connect(self._update_resolution_enabled)
        row3.addWidget(self.resolve_cb)

        row3.addWidget(QLabel("Shift/Reduce:"))
        self.shift_reduce_combo = QComboBox()
        for value in SHIFT_REDUCE_OPTIONS:
            self.shift_reduce_combo.addItem(_SHIFT_REDUCE_LABELS[value], value)
        row3.addWidget(self.shift_reduce_combo)

        row3.addWidget(QLabel("Reduce/Reduce:"))
        self.reduce_reduce_combo = QComboBox()
        for value in REDUCE_REDUCE_OPTIONS:
            self.reduce_reduce_combo.addItem(_REDUCE_REDUCE_LABELS[value], value)
        row3.addWidget(self.reduce_reduce_combo)

        self.show_error_cb = QCheckBox("Show 'Error' cells")
        self.show_error_cb.setToolTip(
            "When enabled, empty ACTION cells display 'Error' instead of "
            "being left blank (as in handwritten notes)."
        )
        row3.addWidget(self.show_error_cb)
        row3.addStretch(1)
        layout.addLayout(row3)

        self.feature_label = QLabel("")
        self.feature_label.setStyleSheet("color: #666;")
        self.feature_label.setWordWrap(True)
        layout.addWidget(self.feature_label)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Enter grammar in BNF format (one production per line).\n\n"
            "Example:\n" + EXAMPLE_GRAMMAR
        )
        self.editor.setTabChangesFocus(False)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.editor, 3)

        self.preview_caption = QLabel("Grammar preview (ordering preserved):")
        self.preview_caption.setStyleSheet("color: #444;")
        layout.addWidget(self.preview_caption)

        variant_row = QHBoxLayout()
        variant_row.addWidget(QLabel("Show:"))
        self.variant_combo = QComboBox()
        variant_row.addWidget(self.variant_combo, 1)
        layout.addLayout(variant_row)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.preview.setMaximumHeight(110)
        self.preview.setPlaceholderText("The grammar actually analysed appears here.")
        layout.addWidget(self.preview, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.status_label)

        self._variants: dict[str, str] = {}
        self.variant_combo.currentTextChanged.connect(self._on_variant_changed)
        self._update_resolution_enabled(False)
        self.set_grammar_text(EXAMPLE_GRAMMAR)
        logger.debug("GrammarEditor initialized")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _make_transform_checkbox(self, text: str, tooltip: str) -> QCheckBox:
        checkbox = QCheckBox(text)
        checkbox.setToolTip(tooltip)
        return checkbox

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_grammar_text(self, text: str) -> None:
        """Replace the editor contents."""
        self.editor.setPlainText(text)

    def grammar_text(self) -> str:
        """Return the current editor contents."""
        return self.editor.toPlainText()

    def selected_parser_type(self) -> str:
        """Return the currently selected parser type."""
        return self.parser_combo.currentText()

    def set_parser_type(self, parser_type: str) -> None:
        """Select the given parser type if present."""
        index = self.parser_combo.findText(parser_type)
        if index >= 0:
            self.parser_combo.setCurrentIndex(index)

    def current_resolution(self) -> ResolutionConfig:
        """Return the currently selected conflict-resolution configuration."""
        return ResolutionConfig(
            enabled=self.resolve_cb.isChecked(),
            shift_reduce=self.shift_reduce_combo.currentData(),
            reduce_reduce=self.reduce_reduce_combo.currentData(),
        )

    def current_options(self) -> GenerateOptions:
        """Return a :class:`GenerateOptions` reflecting the current UI state."""
        return GenerateOptions(
            parser_type=self.selected_parser_type(),
            remove_left_recursion=self.remove_left_recursion_cb.isChecked(),
            left_factoring=self.left_factoring_cb.isChecked(),
            remove_epsilon=self.remove_epsilon_cb.isChecked(),
            remove_unit=self.remove_unit_cb.isChecked(),
            remove_useless=self.remove_useless_cb.isChecked(),
            resolution=self.current_resolution(),
            show_error_cells=self.show_error_cb.isChecked(),
        )

    def set_feature_note(self, note: str) -> None:
        """Show a short note describing the grammar's shape."""
        self.feature_label.setText(note)

    def set_transform_preview(self, text: str) -> None:
        """Show the grammar that was actually analysed."""
        if "Used (after transforms)" in self._variants:
            self._variants["Used (after transforms)"] = text
        else:
            self._variants = {"Used (after transforms)": text}
            self.variant_combo.blockSignals(True)
            self.variant_combo.clear()
            self.variant_combo.addItem("Used (after transforms)")
            self.variant_combo.blockSignals(False)
        self.preview.setPlainText(text)

    def set_grammar_variants(self, variants: dict[str, str]) -> None:
        """Populate the grammar-variant selector.

        Args:
            variants: Ordered mapping of label to BNF text, typically
                ``Original``, ``Left-recursion removed``, ``Left-factored`` and
                ``Used (after transforms)``.
        """
        self._variants = dict(variants)
        preferred = "Used (after transforms)"
        target = preferred if preferred in self._variants else next(
            iter(self._variants), ""
        )
        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()
        for label in self._variants:
            self.variant_combo.addItem(label)
        index = self.variant_combo.findText(target)
        if index >= 0:
            self.variant_combo.setCurrentIndex(index)
        self.variant_combo.blockSignals(False)
        self.preview.setPlainText(self._variants.get(target, ""))

    def set_status(self, message: str, is_error: bool = False) -> None:
        """Show a status message, coloured red on error."""
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: #B00020;")
        else:
            self.status_label.setStyleSheet("color: #1E6B34;")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _update_resolution_enabled(self, enabled: bool) -> None:
        self.shift_reduce_combo.setEnabled(enabled)
        self.reduce_reduce_combo.setEnabled(enabled)

    def _on_variant_changed(self, label: str) -> None:
        """Show the selected grammar variant."""
        self.preview.setPlainText(self._variants.get(label, ""))

    def _on_generate(self) -> None:
        self.generate_requested.emit(self.grammar_text(), self.current_options())