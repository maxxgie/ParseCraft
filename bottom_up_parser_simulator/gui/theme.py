"""Centralised application-wide theme (colours, headers, selection, borders).

This module installs ONE global :class:`~PyQt6.QtWidgets.QApplication`
stylesheet so every tab, table, list, toolbar and modal shares the same look
and feel without each view having to restyle itself.  It is deliberately
side-effect free with respect to program logic: it only touches visual
properties (colours, borders, fonts, padding).

Palette (kept in sync with :mod:`gui.design`):

* headers / primary containers —— charcoal slate ``#1E293B`` with white text;
* selection / hover —— subtle blue ``#E8EEF7`` / ``#DBEAFE``;
* grid / dividers —— light gray ``#CBD5E1``;
* base background —— white ``#FFFFFF``.
"""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# --- tokens ----------------------------------------------------------------
HEADER_BG = "#1E293B"
HEADER_FG = "#F8FAFC"
HEADER_BORDER = "#0F172A"

SELECTION_BG = "#DBEAFE"
SELECTION_FG = "#0F172A"
HOVER_BG = "#F0F4FB"

GRID = "#CBD5E1"
BASE_BG = "#FFFFFF"
ALT_ROW_BG = "#F8FAFC"
BORDER = "#E2E8F0"

TAB_BAR_BG = "#F1F5F9"
TAB_ACTIVE_BG = "#FFFFFF"

FIELD_BG = "#FFFFFF"
FIELD_BORDER = "#CBD5E1"
FIELD_FOCUS = "#2563EB"

# Accent foregrounds used by status labels (kept consistent with the palette).
SUCCESS_FG = "#1B5E20"
ERROR_FG = "#B71C1C"
WARN_FG = "#8A6D00"
MUTED_FG = "#555555"


def build_stylesheet() -> str:
    """Return the global Qt stylesheet string.

    Returns:
        A QSS (Qt Style Sheets) document covering the shared widgets.
    """
    return f"""
    /* ---- base -------------------------------------------------------- */
    QWidget {{
        background-color: {BASE_BG};
        color: #1F2937;
    }}
    QMainWindow, QDialog {{
        background-color: {BASE_BG};
    }}

    /* ---- section / group headers ------------------------------------ */
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        margin-top: 10px;
        padding: 8px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {HEADER_BG};
    }}

    /* ---- tables ------------------------------------------------------ */
    QTableWidget {{
        background-color: {BASE_BG};
        alternate-background-color: {ALT_ROW_BG};
        grid-color: {GRID};
        border: 1px solid {BORDER};
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_FG};
    }}
    QTableWidget::item {{
        padding: 2px 4px;
        border-bottom: 1px solid {BORDER};
    }}
    QTableWidget::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_FG};
    }}
    QHeaderView::section {{
        background-color: {HEADER_BG};
        color: {HEADER_FG};
        font-weight: bold;
        padding: 4px;
        border: 0px;
        border-right: 1px solid {HEADER_BORDER};
        border-bottom: 1px solid {HEADER_BORDER};
    }}
    QTableCornerButton::section {{
        background-color: {HEADER_BG};
        border: 0px;
    }}

    /* ---- lists / trees ---------------------------------------------- */
    QListWidget, QTreeWidget {{
        background-color: {BASE_BG};
        border: 1px solid {BORDER};
        alternate-background-color: {ALT_ROW_BG};
    }}
    QListWidget::item {{
        padding: 3px 6px;
        border-bottom: 1px solid {BORDER};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_FG};
    }}
    QListWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {HOVER_BG};
    }}

    /* ---- inputs ------------------------------------------------------ */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {FIELD_BG};
        border: 1px solid {FIELD_BORDER};
        border-radius: 4px;
        padding: 3px;
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_FG};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {FIELD_FOCUS};
    }}
    QComboBox::drop-down {{
        border: 0px;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {FIELD_BG};
        border: 1px solid {FIELD_BORDER};
        selection-background-color: {SELECTION_BG};
        selection-color: {SELECTION_FG};
    }}

    /* ---- buttons ----------------------------------------------------- */
    QPushButton {{
        background-color: {HEADER_BG};
        color: {HEADER_FG};
        font-weight: bold;
        border: 0px;
        border-radius: 4px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{
        background-color: #334155;
    }}
    QPushButton:pressed {{
        background-color: #0F172A;
    }}
    QPushButton:disabled {{
        background-color: #CBD5E1;
        color: #64748B;
    }}

    /* ---- checkboxes / radios ---------------------------------------- */
    QCheckBox, QRadioButton {{
        color: #1F2937;
        spacing: 6px;
        background: transparent;
    }}
    QCheckBox:disabled, QRadioButton:disabled {{
        color: #94A3B8;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 15px;
        height: 15px;
        border: 2px solid #64748B;
        background: #FFFFFF;
    }}
    QCheckBox::indicator {{
        border-radius: 3px;
    }}
    QRadioButton::indicator {{
        border-radius: 8px;
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border: 2px solid {FIELD_FOCUS};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {FIELD_FOCUS};
        border: 2px solid #1D4ED8;
    }}
    QCheckBox::indicator:focus, QRadioButton::indicator:focus {{
        border: 2px solid {FIELD_FOCUS};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        border: 2px solid #CBD5E1;
        background: #F1F5F9;
    }}

    /* ---- disabled inputs (keep text readable) ----------------------- */
    QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
    QSpinBox:disabled, QComboBox:disabled {{
        background-color: #F1F5F9;
        color: #64748B;
    }}

    /* ---- tabs -------------------------------------------------------- */
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        background: {BASE_BG};
    }}
    QTabBar::tab {{
        background: {TAB_BAR_BG};
        color: #334155;
        border: 1px solid {BORDER};
        border-bottom: 0px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 6px 12px;
        margin-right: 2px;
        font-weight: bold;
    }}
    QTabBar::tab:selected {{
        background: {TAB_ACTIVE_BG};
        color: {HEADER_BG};
        border-bottom: 2px solid {FIELD_FOCUS};
    }}
    QTabBar::tab:hover {{
        background: {HOVER_BG};
    }}

    /* ---- splitters --------------------------------------------------- */
    QSplitter::handle {{
        background-color: {GRID};
    }}
    QSplitter::handle:horizontal {{
        width: 3px;
    }}
    QSplitter::handle:vertical {{
        height: 3px;
    }}

    /* ---- scrollbars -------------------------------------------------- */
    QScrollBar:vertical {{
        background: {BASE_BG};
        width: 12px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #CBD5E1;
        border-radius: 6px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #94A3B8;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {BASE_BG};
        height: 12px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: #CBD5E1;
        border-radius: 6px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: #94A3B8;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ---- toolbars / status ------------------------------------------ */
    QToolBar {{
        background-color: {TAB_BAR_BG};
        border-bottom: 1px solid {BORDER};
        spacing: 4px;
    }}
    QStatusBar {{
        background-color: {TAB_BAR_BG};
        border-top: 1px solid {BORDER};
        color: #334155;
    }}

    /* ---- menus ------------------------------------------------------- */
    QMenuBar {{
        background-color: {TAB_BAR_BG};
        border-bottom: 1px solid {BORDER};
    }}
    QMenuBar::item:selected {{
        background-color: {SELECTION_BG};
    }}
    QMenu {{
        background-color: {FIELD_BG};
        border: 1px solid {BORDER};
    }}
    QMenu::item:selected {{
        background-color: {SELECTION_BG};
        color: {SELECTION_FG};
    }}

    /* ---- tooltips ---------------------------------------------------- */
    QToolTip {{
        background-color: #0F172A;
        color: #F8FAFC;
        border: 0px;
        padding: 3px;
    }}
    """


def apply_theme(app: QApplication) -> None:
    """Install the global theme on ``app`` (idempotent).

    Args:
        app: The running :class:`QApplication`.
    """
    app.setStyleSheet(build_stylesheet())
    # A clean default UI font; grammar views override with a monospace font.
    default = QFont()
    default.setPointSizeF(max(default.pointSizeF(), 9.0))
    app.setFont(default)