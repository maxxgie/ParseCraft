"""Shared colour palette for tables and conflict views.

Colours are soft pastels chosen for comfortable reading, paired with dark
foregrounds so text stays high-contrast in both light and dark UI themes.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor

# --- ACTION table -----------------------------------------------------------
SHIFT_BG = QColor("#BBDEFB")   # soft blue
SHIFT_FG = QColor("#0D47A1")
REDUCE_BG = QColor("#C8E6C9")  # soft green
REDUCE_FG = QColor("#1B5E20")
ACCEPT_BG = QColor("#81C784")  # medium green
ACCEPT_FG = QColor("#1B5E20")
ERROR_BG = QColor("#FFCDD2")   # soft red (real errors)
ERROR_FG = QColor("#B71C1C")
BLANK_BG = QColor("#F5F5F5")   # empty cells
BLANK_FG = QColor("#475569")   # readable slate for placeholders ("—")

# --- GOTO table -------------------------------------------------------------
GOTO_BG = QColor("#D1C4E9")    # soft lavender
GOTO_FG = QColor("#311B92")

# --- Conflict rows ----------------------------------------------------------
RESOLVED_BG = QColor("#A5D6A7")
RESOLVED_FG = QColor("#1B5E20")
UNRESOLVED_BG = QColor("#FFCDD2")
UNRESOLVED_FG = QColor("#B71C1C")


def action_colors(action_type: str) -> tuple[QColor, QColor]:
    """Return ``(background, foreground)`` for an ACTION cell type."""
    return {
        "shift": (SHIFT_BG, SHIFT_FG),
        "reduce": (REDUCE_BG, REDUCE_FG),
        "accept": (ACCEPT_BG, ACCEPT_FG),
        "error": (ERROR_BG, ERROR_FG),
    }.get(action_type, (ERROR_BG, ERROR_FG))