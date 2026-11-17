"""Canonical Collection tab: grouped LR(0)/SLR(1) state table.

The tab shows every automaton state in a single four-column table
(``State`` / ``Config State`` / ``Consume`` / ``Next State``).  All items that
belong to the same state are grouped together: the state number is shown once
on the first row of the group (via ``setSpan``), kernel items are bold with a
left accent bar, and the dot ``•`` is rendered in an accent colour so the
parser position is immediately readable.  The right-hand explanation panel is
kept and is refreshed whenever a state row is selected.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QRectF,
    Qt,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_config import get_logger
from core.table_builder import AUGMENTED_START, assign_production_numbers

logger = get_logger(__name__)

# --- palette ---------------------------------------------------------------
DOT_COLOR = QColor("#C2410C")          # accent orange for the dot "•"
KERNEL_ACCENT = QColor("#2563EB")      # blue bar beside kernel items
KERNEL_FG = QColor("#1E3A8A")
CLOSURE_FG = QColor("#1F2937")
STATE_BG = QColor("#E8EEF7")           # active state-group tint
STATE_BG_HOVER = QColor("#F0F4FB")     # hover tint for a state group
SELECTION_BG = QColor("#DBEAFE")       # light-blue selected-row fill (dark text)
GRID_BG = QColor("#FFFFFF")
CONSUME_FG = QColor("#0F766E")         # teal for the Consume column
NEXT_FG = QColor("#7C3AED")            # violet for the Next State column
REDUCE_BG = QColor("#C8E6C9")
REDUCE_FG = QColor("#1B5E20")
ACCEPT_BG = QColor("#81C784")
ACCEPT_FG = QColor("#1B5E20")
DIVIDER_COLOR = QColor("#CBD5E1")
PLACEHOLDER_FG = QColor("#475569")     # readable slate for "—" placeholders


def _mono_font() -> QFont:
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(max(font.pointSizeF(), 9.5))
    return font


class _Item:
    """Plain data holder for one table row (one LR item inside a state)."""

    __slots__ = (
        "state_id",
        "config_html",
        "consume",
        "consume_kind",
        "next_text",
        "next_kind",
        "target_state",
        "is_kernel",
        "is_first_row",
        "row_span",
    )

    def __init__(
        self,
        state_id: int,
        config_html: str,
        consume: str,
        consume_kind: str,
        next_text: str,
        next_kind: str,
        target_state: int | None,
        is_kernel: bool,
        is_first_row: bool,
        row_span: int,
    ) -> None:
        self.state_id = state_id
        self.config_html = config_html
        self.consume = consume
        self.consume_kind = consume_kind
        self.next_text = next_text
        self.next_kind = next_kind
        self.target_state = target_state
        self.is_kernel = is_kernel
        self.is_first_row = is_first_row
        self.row_span = row_span


class _ConfigDelegate(QStyledItemDelegate):
    """Render the ``Config State`` cell with a coloured dot and kernel styling."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        item = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(item, _Item):
            super().paint(painter, option, index)
            return

        painter.save()
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, SELECTION_BG)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, STATE_BG_HOVER)

        # Left accent bar for kernel items.
        if item.is_kernel:
            painter.fillRect(
                rect.left(), rect.top(), 3, rect.height(), KERNEL_ACCENT
            )

        doc = QTextDocument()
        doc.setHtml(item.config_html)
        doc.setDefaultFont(_mono_font())
        margin = 6 if item.is_kernel else 8
        painter.translate(rect.left() + margin, rect.top())
        # Available drawing area in the translated coordinate system.
        clip = QRectF(0.0, 0.0, rect.width() - margin, rect.height())
        doc.drawContents(painter, clip)
        painter.restore()


class LRStatesView(QWidget):
    """Grouped canonical-collection table with a sticky explanation panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see LR states.")
        self.header.setStyleSheet("color: #555;")

        top_row = QHBoxLayout()
        top_row.addWidget(self.header, 1)
        self.grammar_caption = QLabel("Used grammar:")
        self.grammar_caption.setStyleSheet("color: #444;")
        top_row.addWidget(self.grammar_caption, 0)
        self.grammar_view = QPlainTextEdit()
        self.grammar_view.setReadOnly(True)
        self.grammar_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.grammar_view.setMaximumHeight(110)
        self.grammar_view.setMinimumWidth(280)
        self.grammar_view.setPlaceholderText("The grammar used appears here.")
        self.grammar_view.setFont(_mono_font())
        top_row.addWidget(self.grammar_view, 0)
        layout.addLayout(top_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- left: the canonical collection table ------------------------
        table_wrap = QWidget()
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["State", "Config State", "Consume", "Next State"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(
            "QTableWidget { background: %s; alternate-background-color: %s; }"
            "QTableWidget::item { padding: 2px 4px; }"
            % (GRID_BG.name(), STATE_BG_HOVER.name())
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)
        self.table.setItemDelegateForColumn(1, _ConfigDelegate(self.table))
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        table_layout.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.detail.setPlaceholderText(
            "Select a state row to see its kernel items, closure steps and "
            "GOTO/reduction logic."
        )
        splitter.addWidget(table_wrap)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([700, 320])
        layout.addWidget(splitter, 1)

        self._analysis = None
        self._rule_numbers: dict[tuple[str, tuple[str, ...]], int] = {}
        self._rows_by_state: dict[int, int] = {}
        self._item_rows: list[_Item] = []
        self._current_state: int | None = None
        self._suppress = False

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the view."""
        self._analysis = None
        self._rule_numbers = {}
        self._rows_by_state = {}
        self._item_rows = []
        self._current_state = None
        self.table.clearContents()
        self.table.setRowCount(0)
        self.detail.clear()
        self.grammar_view.clear()
        self.header.setText("Generate a grammar to see LR states.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the grouped canonical-collection table."""
        self._analysis = analysis
        automaton = analysis.automaton
        aug = getattr(automaton, "augmented_grammar", None) or automaton.grammar
        self._rule_numbers, _ = assign_production_numbers(
            automaton.grammar, aug.start_symbol
        )

        self.grammar_view.setPlainText(analysis.grammar_text)
        self._suppress = True
        self.table.clearContents()
        self.table.setRowCount(0)
        self._rows_by_state = {}
        self._item_rows = []
        self._current_state = None

        items: list[_Item] = []
        for state in automaton.states:
            ordered = state.sorted_items()
            kernel = automaton.kernel_items(state)
            kernel_keys = {item.key() for item in kernel}
            span = max(len(ordered), 1)
            first_row = len(items)
            width = max((len(it.lhs) for it in ordered), default=0)
            for offset, item in enumerate(ordered):
                consume_sym = item.next_symbol()
                target = (
                    state.transitions.get(consume_sym)
                    if consume_sym is not None
                    else None
                )
                if item.is_complete():
                    consume = "—"
                    consume_kind = "blank"
                    if item.lhs == aug.start_symbol:
                        next_text = "Accept"
                        next_kind = "accept"
                    else:
                        rule = self._rule_numbers.get((item.lhs, item.rhs))
                        next_text = f"r{rule}" if rule is not None else "—"
                        next_kind = "reduce"
                    target_state = None
                else:
                    consume = consume_sym
                    consume_kind = "consume"
                    if target is not None:
                        next_text = str(target)
                        next_kind = "goto"
                    else:
                        next_text = "—"
                        next_kind = "blank"
                    target_state = target
                items.append(
                    _Item(
                        state_id=state.state_id,
                        config_html=self._config_html(item, width, item.key() in kernel_keys),
                        consume=consume,
                        consume_kind=consume_kind,
                        next_text=next_text,
                        next_kind=next_kind,
                        target_state=target_state,
                        is_kernel=item.key() in kernel_keys,
                        is_first_row=(offset == 0),
                        row_span=span,
                    )
                )
            if first_row < len(items) - 0:
                self._rows_by_state[state.state_id] = first_row

        self.table.setRowCount(len(items))
        self._item_rows = items
        for row, entry in enumerate(items):
            self._populate_row(row, entry)

        self._suppress = False
        self.header.setText(
            f"{analysis.parser_type}: {len(automaton.states)} states "
            f"({len(automaton.transitions)} transitions)"
            + ("  ⚠ merged (LALR)" if getattr(automaton, "merged", False) else "")
        )
        self.header.setStyleSheet("color: #333;")

        if items:
            self._select_state(items[0].state_id)
        else:
            self.detail.clear()

    # ------------------------------------------------------------------
    def _config_html(self, item, lhs_width: int, is_kernel: bool) -> str:
        """Build the rich-text body for a ``Config State`` cell."""
        lhs = item.lhs.ljust(lhs_width) if lhs_width else item.lhs
        before = " ".join(item.rhs[: item.dot])
        after = " ".join(item.rhs[item.dot :])
        if not before and not after:
            body = "<span style='color:%s;font-weight:bold'>•</span>" % DOT_COLOR.name()
        elif not before:
            body = (
                "<span style='color:%s;font-weight:bold'>•</span> %s"
                % (DOT_COLOR.name(), self._esc(after))
            )
        elif not after:
            body = "%s<span style='color:%s;font-weight:bold'>•</span>" % (
                self._esc(before),
                DOT_COLOR.name(),
            )
        else:
            body = "%s <span style='color:%s;font-weight:bold'>•</span> %s" % (
                self._esc(before),
                DOT_COLOR.name(),
                self._esc(after),
            )

        lookahead = ""
        if item.lookahead:
            lookahead = (
                " , <span style='color:#6B7280'>%s</span>" % self._esc(item.lookahead)
            )
            return (
                "<span style='color:%s'>[%s -> %s%s]</span>"
                % (
                    KERNEL_FG.name() if is_kernel else CLOSURE_FG.name(),
                    self._esc(lhs),
                    body,
                    lookahead,
                )
            )
        weight = "font-weight:600" if is_kernel else ""
        return "<span style='color:%s;%s'>%s -> %s</span>" % (
            KERNEL_FG.name() if is_kernel else CLOSURE_FG.name(),
            weight,
            self._esc(lhs),
            body,
        )

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _populate_row(self, row: int, entry: _Item) -> None:
        # State badge (merged into a single cell via setSpan below).
        state_item = QTableWidgetItem(str(entry.state_id) if entry.is_first_row else "")
        state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if entry.is_first_row:
            fnt = QFont()
            fnt.setBold(True)
            state_item.setFont(fnt)
            state_item.setForeground(KERNEL_FG)
        state_item.setData(Qt.ItemDataRole.UserRole, entry)
        state_item.setToolTip(f"State {entry.state_id}")
        self.table.setItem(row, 0, state_item)

        # Config State (rendered by the delegate).
        config_item = QTableWidgetItem()
        config_item.setData(Qt.ItemDataRole.UserRole, entry)
        self.table.setItem(row, 1, config_item)

        consume_item = QTableWidgetItem(entry.consume)
        consume_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        consume_item.setFont(_mono_font())
        if entry.consume_kind == "consume":
            consume_item.setForeground(CONSUME_FG)
        else:
            consume_item.setForeground(PLACEHOLDER_FG)
        consume_item.setData(Qt.ItemDataRole.UserRole, entry)
        self.table.setItem(row, 2, consume_item)

        next_item = QTableWidgetItem(entry.next_text)
        next_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        next_item.setFont(_mono_font())
        fnt = QFont()
        fnt.setBold(True)
        next_item.setFont(fnt)
        if entry.next_kind == "accept":
            next_item.setBackground(ACCEPT_BG)
            next_item.setForeground(ACCEPT_FG)
        elif entry.next_kind == "reduce":
            next_item.setBackground(REDUCE_BG)
            next_item.setForeground(REDUCE_FG)
        elif entry.next_kind == "goto":
            next_item.setForeground(NEXT_FG)
        else:
            next_item.setForeground(PLACEHOLDER_FG)
        next_item.setData(Qt.ItemDataRole.UserRole, entry)
        next_item.setToolTip(
            f"Click to jump to State {entry.target_state}"
            if entry.target_state is not None
            else ""
        )
        self.table.setItem(row, 3, next_item)

        if entry.is_first_row and entry.row_span > 1:
            self.table.setSpan(row, 0, entry.row_span, 1)

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        if self._suppress:
            return
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows:
            return
        row = min(rows)
        if row >= len(self._item_rows):
            return
        self._select_state(self._item_rows[row].state_id)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._item_rows):
            return
        entry = self._item_rows[row]
        if _col == 3 and entry.target_state is not None:
            self._jump_to_state(entry.target_state)
            return
        self._select_state(entry.state_id)

    def _select_state(self, state_id: int) -> None:
        self._current_state = state_id
        first_row = self._rows_by_state.get(state_id)
        if first_row is None:
            return
        # Find the last row of this state's group.
        last_row = first_row
        total = len(self._item_rows)
        while (
            last_row + 1 < total
            and self._item_rows[last_row + 1].state_id == state_id
        ):
            last_row += 1
        # Select the whole group through the selection model.  (Loop calling
        # ``selectRow`` would keep only the last row under a single-selection
        # mode, so the clicked row never appeared to respond.)
        self._suppress = True
        self.table.clearSelection()
        selection = QItemSelection()
        model = self.table.model()
        selection.select(model.index(first_row, 0), model.index(last_row, 2))
        self.table.selectionModel().select(
            selection,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.table.scrollToItem(self.table.item(first_row, 0))
        self._suppress = False
        self._show_state(state_id)

    def _jump_to_state(self, state_id: int) -> None:
        first_row = self._rows_by_state.get(state_id)
        if first_row is None:
            return
        self._select_state(state_id)
        self.table.setCurrentCell(first_row, 0)
        self.table.scrollToItem(self.table.item(first_row, 0))

    def _show_state(self, state_id: int) -> None:
        if self._analysis is None:
            return
        automaton = self._analysis.automaton
        state = automaton.get_state(state_id)
        kernel = automaton.kernel_items(state)
        kernel_keys = {item.key() for item in kernel}

        width = max((len(item.lhs) for item in state.sorted_items()), default=0)
        lines = [
            f"STATE {state_id}",
            "=" * 48,
            "",
            "Kernel items:",
            "",
        ]
        kernel_sorted = [
            it for it in state.sorted_items() if it.key() in kernel_keys
        ]
        if kernel_sorted:
            lines.extend(it.to_string(lhs_width=width) for it in kernel_sorted)
        else:
            lines.append("  (kernel = whole state: initial closure)")
        lines.append("")
        lines.append("Closure items:")
        lines.append("")
        closure_only = [
            it for it in state.sorted_items() if it.key() not in kernel_keys
        ]
        if closure_only:
            lines.extend(it.to_string(lhs_width=width) for it in closure_only)
        else:
            lines.append("  (none — every item is in the kernel)")
        lines.append("")
        lines.append("Transitions:")
        lines.append("")
        lines.append(f"{'Consume':<12}Next State")
        lines.append(f"{'-' * 12}{'-' * 11}")
        if state.transitions:
            for symbol, target in state.transitions.items():
                lines.append(f"{symbol:<12}{target}")
        else:
            lines.append("  (no outgoing transitions)")

        # Reduction / acceptance actions, when the state has completed items.
        complete = [it for it in state.sorted_items() if it.is_complete()]
        if complete:
            lines.append("")
            lines.append("Reductions / Accept:")
            lines.append("")
            for it in complete:
                if it.lhs == automaton.augmented_grammar.start_symbol:
                    lines.append("  ACCEPT  (augmented start production)")
                else:
                    rule = self._rule_numbers.get((it.lhs, it.rhs))
                    tag = f"r{rule}" if rule is not None else "?"
                    body = " ".join(it.rhs) if it.rhs else "ε"
                    lines.append(f"  {tag}  {it.lhs} -> {body}")

        self.detail.setPlainText("\n".join(lines))