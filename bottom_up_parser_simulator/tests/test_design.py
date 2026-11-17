"""Tests for the shared UI design system helpers."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QSplitter, QTableWidget

from gui import design


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_mono_font_is_monospace():
    font = design.mono_font()
    assert font.styleHint() == font.StyleHint.Monospace


def test_mono_font_bold_flag():
    assert design.mono_font(bold=True).bold() is True
    assert design.mono_font(bold=False).bold() is False


def test_cell_defaults(app):
    item = design.cell("5")
    assert item.text() == "5"
    assert item.textAlignment() & Qt.AlignmentFlag.AlignCenter


def test_cell_with_colors(app):
    item = design.cell("r1", design.REDUCE_BG, design.REDUCE_FG, bold=True, mono=True)
    assert item.foreground().color() == design.REDUCE_FG
    assert item.font().bold() is True


def test_cell_left_align(app):
    item = design.cell("E -> E + T", align_center=False)
    alignment = item.textAlignment()
    assert alignment & Qt.AlignmentFlag.AlignLeft


def test_make_table_columns_and_stretch(app):
    table = design.make_table(["State", "Config", "Next"], stretch_cols={1})
    assert table.columnCount() == 3
    assert table.horizontalHeaderItem(0).text() == "State"


def test_make_split_body_returns_splitter(app):
    table = QTableWidget(0, 1)
    detail = design.make_detail_panel("hint")
    splitter = design.make_split_body(table, detail)
    assert isinstance(splitter, QSplitter)
    assert splitter.count() == 2


def test_make_detail_panel_readonly(app):
    detail = design.make_detail_panel("pick a row")
    assert detail.isReadOnly() is True
    detail.setPlainText("hello")
    assert detail.toPlainText() == "hello"


def test_style_table_applies_stylesheet(app):
    table = QTableWidget(0, 2)
    design.style_table(table)
    assert table.styleSheet() != ""
    assert design.HEADER_BG in table.styleSheet()


def test_header_label_wraps(app):
    label = design.header_label("A fairly long header that should wrap nicely")
    assert label.wordWrap() is True