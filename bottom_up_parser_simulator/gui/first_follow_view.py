"""FIRST / FOLLOW set display.

A single styled table (``Production / Symbol`` / ``FIRST`` / ``FOLLOW``) on the
left and a sticky Explanation panel on the right.  The panel reconstructs the
step-by-step derivation rules (which productions contribute each terminal, how
``$`` and ``ε`` are added) from the grammar and the already-computed sets; the
underlying FIRST/FOLLOW computation itself is not modified.
"""

from __future__ import annotations

from typing import Dict, List, Set

from PyQt6.QtCore import QModelIndex, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from gui.grammar_reference import GrammarReferencePane
from gui.settings import EPSILON

logger = get_logger(__name__)

# --- palette ---------------------------------------------------------------
DOLLAR_COLOR = QColor("#B45309")        # amber for the EOF marker "$"
EPSILON_COLOR = QColor("#7C3AED")       # violet for the epsilon marker "ε"
KERNEL_FG = QColor("#1E3A8A")           # bold non-terminal symbols
TERMINAL_FG = QColor("#0F766E")         # teal terminal symbols
STATE_BG_HOVER = QColor("#F0F4FB")
SELECTION_BG = QColor("#DBEAFE")        # light-blue selected-row fill (dark text)


def _mono_font(bold: bool = False) -> QFont:
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(max(font.pointSizeF(), 9.5))
    if bold:
        font.setBold(True)
    return font


def _format_set(values: Set[str]) -> str:
    """Format a set of symbols as ``{ a, b, c }``."""
    if not values:
        return "{ }"
    return "{ " + ", ".join(sorted(values)) + " }"


class _SetDelegate(QStyledItemDelegate):
    """Render a ``{ ... }`` set, colouring the ``$`` and ``ε`` markers."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text:
            super().paint(painter, option, index)
            return

        painter.save()
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, SELECTION_BG)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, STATE_BG_HOVER)

        doc = QTextDocument()
        doc.setHtml(self._html(text))
        doc.setDefaultFont(_mono_font())
        margin = 4
        painter.translate(rect.left() + margin, rect.top())
        clip = QRectF(0.0, 0.0, max(rect.width() - 2 * margin, 1.0), rect.height())
        doc.drawContents(painter, clip)
        painter.restore()

    @staticmethod
    def _html(text: str) -> str:
        esc = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        esc = esc.replace(
            "$",
            "<span style='color:%s;font-weight:bold'>$</span>" % DOLLAR_COLOR.name(),
        )
        esc = esc.replace(
            EPSILON,
            "<span style='color:%s;font-weight:bold'>%s</span>"
            % (EPSILON_COLOR.name(), EPSILON),
        )
        # Always paint an explicit dark base colour.  A bare QTextDocument draws
        # its text with the painter's default pen (the palette Text colour), so
        # on systems whose palette text colour is light the set contents become
        # invisible on the light cell background.  Pinning the base colour keeps
        # the sets readable regardless of the active palette.
        return "<span style='color:#1F2937'>%s</span>" % esc


class FirstFollowView(QWidget):
    """A table showing FIRST and FOLLOW sets for each grammar symbol."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.summary = QLabel("Generate a grammar to see FIRST/FOLLOW sets.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #555;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Production / Symbol", "FIRST", "FOLLOW"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setFont(_mono_font())
        set_delegate = _SetDelegate(self.table)
        self.table.setItemDelegateForColumn(1, set_delegate)
        self.table.setItemDelegateForColumn(2, set_delegate)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # Right column: the grammar reference plus a sticky explanation panel
        # that shows the derivation rules for the selected symbol.
        self.grammar = GrammarReferencePane(max_height=140)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.detail.setFont(_mono_font())
        self.detail.setPlaceholderText(
            "Select a symbol to see how its FIRST / FOLLOW set was computed."
        )

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.addWidget(self.grammar, 0)
        right_layout.addWidget(self.detail, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        splitter.setSizes([680, 360])
        layout.addWidget(splitter, 1)

        self._analysis = None
        self._rows: list[tuple[str, bool]] = []

    def clear(self) -> None:
        """Reset the view to its empty state."""
        self._analysis = None
        self._rows = []
        self.table.clearContents()
        self.table.setRowCount(0)
        self.grammar.clear()
        self.detail.clear()
        self.summary.setText("Generate a grammar to see FIRST/FOLLOW sets.")
        self.summary.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Populate the table from an :class:`~core.engine.AnalysisResult`."""
        self._analysis = analysis
        first = analysis.first
        follow = analysis.follow
        non_terminals = sorted(analysis.grammar.non_terminals)
        terminals = sorted(analysis.grammar.terminals)
        self.grammar.set_grammar(analysis.grammar_text)

        rows: list[tuple[str, bool]] = []
        for nt in non_terminals:
            rows.append((nt, True))
        for t in terminals:
            rows.append((t, False))
        self._rows = rows

        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row, (symbol, is_nt) in enumerate(rows):
            fset = first.get(symbol, set())
            folset = follow.get(symbol, set())

            sym_item = QTableWidgetItem(symbol)
            sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            sym_item.setFont(_mono_font(bold=is_nt))
            sym_item.setForeground(KERNEL_FG if is_nt else TERMINAL_FG)
            sym_item.setToolTip(
                self._symbol_tooltip(symbol, is_nt)
            )
            sym_item.setData(Qt.ItemDataRole.UserRole, row)

            first_item = QTableWidgetItem(_format_set(fset))
            first_item.setData(Qt.ItemDataRole.UserRole, row)

            follow_text = _format_set(folset) if (folset or is_nt) else "-"
            follow_item = QTableWidgetItem(follow_text)
            follow_item.setData(Qt.ItemDataRole.UserRole, row)

            self.table.setItem(row, 0, sym_item)
            self.table.setItem(row, 1, first_item)
            self.table.setItem(row, 2, follow_item)

        self.summary.setText(
            f"{len(non_terminals)} non-terminals, {len(terminals)} terminals. "
            f"End marker is '$'; epsilon is '{EPSILON}'."
        )
        self.summary.setStyleSheet("color: #333;")
        if rows:
            self.table.selectRow(0)

    # ------------------------------------------------------------------
    def _symbol_tooltip(self, symbol: str, is_nt: bool) -> str:
        if not is_nt:
            return f"{symbol} (terminal)"
        grammar = self._analysis.grammar
        bodies = grammar.productions.get(symbol, [])
        if not bodies:
            return f"{symbol} (non-terminal)"
        prods = "  |  ".join(
            f"{symbol} -> {' '.join(rhs) if rhs else EPSILON}" for rhs in bodies
        )
        return prods

    def _on_selection_changed(self) -> None:
        selected = self.table.selectedIndexes()
        if not selected:
            return
        row = min(idx.row() for idx in selected)
        if 0 <= row < len(self._rows):
            self._show_symbol(self._rows[row][0])

    def _show_symbol(self, symbol: str) -> None:
        if self._analysis is None:
            return
        grammar = self._analysis.grammar
        first = self._analysis.first
        follow = self._analysis.follow
        is_nt = symbol in grammar.non_terminals

        lines: List[str] = [
            f"SYMBOL {symbol}",
            "=" * 48,
            "",
            "Kind: " + ("non-terminal" if is_nt else "terminal"),
            "",
            f"FIRST({symbol}) = {_format_set(first.get(symbol, set()))}",
        ]

        if is_nt:
            lines.append("")
            lines.append("Productions:")
            lines.append("")
            for rhs in grammar.productions.get(symbol, []):
                lines.append(f"  {symbol} -> {' '.join(rhs) if rhs else EPSILON}")

            lines.append("")
            lines.extend(self._first_derivation(symbol, first))

            lines.append("")
            lines.append(f"FOLLOW({symbol}) = {_format_set(follow.get(symbol, set()))}")
            lines.append("")
            lines.extend(self._follow_derivation(symbol, first, follow))
        else:
            lines.append("")
            lines.append(
                f"  FIRST({symbol}) = {{ {symbol} }} by definition (a terminal)."
            )
            lines.append(f"FOLLOW({symbol}) = n/a (terminals have no FOLLOW set).")

        self.detail.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Derivation reconstruction (presentation only; uses the computed sets).
    # ------------------------------------------------------------------
    def _first_derivation(
        self, symbol: str, first: Dict[str, Set[str]]
    ) -> List[str]:
        grammar = self._analysis.grammar
        lines: List[str] = ["FIRST derivation (per production):", ""]
        for rhs in grammar.productions.get(symbol, []):
            body = " ".join(rhs) if rhs else EPSILON
            lines.append(f"  {symbol} -> {body}")
            if not rhs:
                lines.append(f"    ε-body ⇒ add {EPSILON}")
                continue
            parts: List[str] = []
            all_nullable = True
            for sym in rhs:
                if sym == EPSILON:
                    parts.append(f"{EPSILON}")
                    all_nullable = True
                    break
                fset = first.get(sym, set())
                non_eps = sorted(s for s in fset if s != EPSILON)
                shown = ", ".join(non_eps) if non_eps else "∅"
                parts.append(f"FIRST({sym}) − {{ε}} = {{ {shown} }}")
                if EPSILON not in fset:
                    all_nullable = False
                    break
            detail = "; ".join(parts)
            lines.append(f"    ⇒ add {detail}")
            if all_nullable:
                lines.append(f"    body is nullable ⇒ add {EPSILON}")
        return lines

    def _follow_derivation(
        self,
        symbol: str,
        first: Dict[str, Set[str]],
        follow: Dict[str, Set[str]],
    ) -> List[str]:
        grammar = self._analysis.grammar
        lines: List[str] = ["FOLLOW derivation (contributions):", ""]
        if grammar.start_symbol == symbol:
            lines.append("  • start symbol ⇒ add $ (EOF marker)")
        found = False
        for lhs, rhs_list in grammar.productions.items():
            for rhs in rhs_list:
                for i, sym in enumerate(rhs):
                    if sym != symbol:
                        continue
                    found = True
                    prod = f"{lhs} -> {' '.join(rhs) if rhs else EPSILON}"
                    rest = rhs[i + 1:]
                    if not rest:
                        lines.append(
                            f"  • {prod}: {symbol} at end ⇒ add FOLLOW({lhs})"
                        )
                        continue
                    first_rest: Set[str] = set()
                    all_nullable = True
                    for s in rest:
                        first_rest |= (first.get(s, set()) - {EPSILON})
                        if EPSILON not in first.get(s, set()):
                            all_nullable = False
                            break
                    shown = ", ".join(sorted(first_rest)) if first_rest else "∅"
                    lines.append(
                        f"  • {prod}: add FIRST({' '.join(rest)}) − {{ε}} = {{ {shown} }}"
                    )
                    if all_nullable:
                        lines.append(f"      rest nullable ⇒ also add FOLLOW({lhs})")
        if not found and grammar.start_symbol != symbol:
            lines.append("  (no production places this symbol on a right-hand side)")
        return lines