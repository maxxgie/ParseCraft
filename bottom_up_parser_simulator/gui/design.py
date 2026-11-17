"""Shared UI design system for every analysis tab.

Centralises the palette, typography, table-header styling and split-pane
construction so that the Canonical Collection, Parsing Table, FIRST/FOLLOW,
State Transitions, Validation, LL(1) and Conflict tabs all share one look and
feel.

The reference layout (from the Canonical Collection tab) is a two-column
:class:`~PyQt6.QtWidgets.QSplitter`:

* **left (60-70%)** — a grouped data table with a dark header, monospace
  symbols, coloured action badges and per-state row grouping;
* **right (30-40%)** — a sticky, read-only explanation panel that refreshes
  when a row/state is selected.
"""

from __future__ import annotations

from typing import Iterable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- palette ---------------------------------------------------------------
# Header (dark bar with bold white text).
HEADER_BG = "#1E293B"
HEADER_FG = "#F8FAFC"

# Dot / accent colours used by the item renderer.
DOT_COLOR = QColor("#C2410C")          # accent orange for the dot "•"
KERNEL_ACCENT = QColor("#2563EB")      # blue bar beside kernel items
KERNEL_FG = QColor("#1E3A8A")
CLOSURE_FG = QColor("#1F2937")
CONSUME_FG = QColor("#0F766E")         # teal for the Consume column
NEXT_FG = QColor("#7C3AED")            # violet for the Next State column

# State-group tints.
STATE_BG = QColor("#E8EEF7")           # active state-group tint
STATE_BG_HOVER = QColor("#F0F4FB")     # hover tint for a state group
GRID_BG = QColor("#FFFFFF")

# Action badges.
SHIFT_BG = QColor("#BBDEFB")
SHIFT_FG = QColor("#0D47A1")
REDUCE_BG = QColor("#C8E6C9")
REDUCE_FG = QColor("#1B5E20")
ACCEPT_BG = QColor("#81C784")
ACCEPT_FG = QColor("#1B5E20")
ERROR_BG = QColor("#FFCDD2")
ERROR_FG = QColor("#B71C1C")
BLANK_BG = QColor("#F5F5F5")
BLANK_FG = QColor("#9E9E9E")

# GOTO / transition colours.
GOTO_BG = QColor("#D1C4E9")
GOTO_FG = QColor("#311B92")

# Conflict resolution colours.
RESOLVED_BG = QColor("#A5D6A7")
RESOLVED_FG = QColor("#1B5E20")
UNRESOLVED_BG = QColor("#FFCDD2")
UNRESOLVED_FG = QColor("#B71C1C")

# Validation / level badges.
OK_BG = QColor("#E8F5E9")
OK_FG = QColor("#1B5E20")
FAIL_BG = QColor("#FFEBEE")
FAIL_FG = QColor("#B71C1C")
WARN_BG = QColor("#FFF3CD")
WARN_FG = QColor("#8A6D00")
INFO_BG = QColor("#CFE2FF")
INFO_FG = QColor("#0D47A1")

DIVIDER_COLOR = QColor("#CBD5E1")


def mono_font(bold: bool = False) -> QFont:
    """Return the shared monospace font used by every data table."""
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(max(font.pointSizeF(), 9.5))
    if bold:
        font.setBold(True)
    return font


def style_table(table: QTableWidget) -> None:
    """Apply the shared dark-header / monospace / grid look to a table.

    Call this after the headers and column count are set up.

    Args:
        table: The table to style.
    """
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(False)
    table.setStyleSheet(
        "QTableWidget {"
        "  background: %s;"
        "  grid-color: %s;"
        "  selection-background-color: %s;"
        "  selection-color: #0F172A;"
        "}"
        "QHeaderView::section {"
        "  background-color: %s;"
        "  color: %s;"
        "  font-weight: bold;"
        "  padding: 4px;"
        "  border: 0px solid #0F172A;"
        "  border-right: 1px solid #334155;"
        "}"
        % (GRID_BG.name(), DIVIDER_COLOR.name(), STATE_BG.name(),
           HEADER_BG, HEADER_FG)
    )


def cell(
    text: str,
    background: Optional[QColor] = None,
    foreground: Optional[QColor] = None,
    bold: bool = False,
    mono: bool = False,
    align_center: bool = True,
    tooltip: Optional[str] = None,
) -> QTableWidgetItem:
    """Create a styled :class:`QTableWidgetItem` with the shared defaults.

    Args:
        text: Cell text.
        background: Optional background colour.
        foreground: Optional foreground colour.
        bold: Whether to use a bold font.
        mono: Whether to use the shared monospace font.
        align_center: Centre the text (tables are mostly numeric/symbolic).
        tooltip: Optional tooltip.

    Returns:
        A configured table item.
    """
    item = QTableWidgetItem(text)
    item.setTextAlignment(
        Qt.AlignmentFlag.AlignCenter if align_center
        else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    if background is not None:
        item.setBackground(background)
    if foreground is not None:
        item.setForeground(foreground)
    if mono:
        item.setFont(mono_font(bold=bold))
    elif bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    if tooltip is not None:
        item.setToolTip(tooltip)
    return item


def header_label(text: str) -> QLabel:
    """Return a header label with the shared muted colour."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #555;")
    return label


def make_detail_panel(placeholder: str) -> QTextEdit:
    """Create the right-hand explanation panel (read-only, sticky)."""
    detail = QTextEdit()
    detail.setReadOnly(True)
    detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    detail.setPlaceholderText(placeholder)
    return detail


def make_grammar_caption(text: str = "Used grammar:") -> QLabel:
    """Return the small caption label shown above the grammar reference."""
    caption = QLabel(text)
    caption.setStyleSheet("color: #444;")
    return caption


def make_split_body(
    table: QWidget,
    detail: QWidget,
    *,
    table_ratio: int = 68,
    detail_ratio: int = 32,
    table_sizes: Optional[Iterable[int]] = None,
    detail_sizes: Optional[Iterable[int]] = None,
) -> QSplitter:
    """Build the standard two-column splitter: table left, detail right.

    Args:
        table: The left-hand widget (usually a table).
        detail: The right-hand explanation panel.
        table_ratio: Stretch factor for the left column.
        detail_ratio: Stretch factor for the right column.
        table_sizes: Optional initial sizes for the left column.
        detail_sizes: Optional initial sizes for the right column.

    Returns:
        A configured horizontal :class:`QSplitter`.
    """
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(table)
    splitter.addWidget(detail)
    splitter.setStretchFactor(0, table_ratio)
    splitter.setStretchFactor(1, detail_ratio)
    left = list(table_sizes) if table_sizes is not None else [720]
    right = list(detail_sizes) if detail_sizes is not None else [340]
    splitter.setSizes(left + right)
    return splitter


def make_table(
    columns: Iterable[str],
    *,
    stretch_cols: Optional[Iterable[int]] = None,
) -> QTableWidget:
    """Create a styled table with the given column headers.

    Args:
        columns: Column header labels.
        stretch_cols: Indices of columns that should stretch (default: last).

    Returns:
        A configured :class:`QTableWidget` ready for rows.
    """
    from PyQt6.QtWidgets import QHeaderView

    cols = list(columns)
    table = QTableWidget(0, len(cols))
    table.setHorizontalHeaderLabels(cols)
    header = table.horizontalHeader()
    stretch = set(stretch_cols) if stretch_cols is not None else {len(cols) - 1}
    for i in range(len(cols)):
        header.setSectionResizeMode(
            i,
            QHeaderView.ResizeMode.Stretch
            if i in stretch
            else QHeaderView.ResizeMode.ResizeToContents,
        )
    style_table(table)
    return table