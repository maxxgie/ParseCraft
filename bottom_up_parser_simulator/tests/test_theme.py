"""Tests for the global application theme."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from gui import theme


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.setStyleSheet("")


def test_build_stylesheet_contains_dark_header(app):
    sheet = theme.build_stylesheet()
    assert theme.HEADER_BG in sheet
    assert "QHeaderView::section" in sheet


def test_build_stylesheet_contains_selection(app):
    sheet = theme.build_stylesheet()
    assert "selection-background-color" in sheet
    assert theme.SELECTION_BG in sheet


def test_build_stylesheet_contains_splitter_handle(app):
    sheet = theme.build_stylesheet()
    assert "QSplitter::handle" in sheet


def test_apply_theme_sets_stylesheet(app):
    theme.apply_theme(app)
    assert app.styleSheet() != ""
    assert theme.HEADER_BG in app.styleSheet()


def test_apply_theme_is_idempotent(app):
    theme.apply_theme(app)
    first = app.styleSheet()
    theme.apply_theme(app)
    assert app.styleSheet() == first