"""Tests for the generated-parser CodeView tab."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from gui.code_view import CodeView, PythonHighlighter


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    v = CodeView()
    yield v
    v.deleteLater()


def test_empty_view_state(view):
    assert not view.copy_button.isEnabled()
    assert not view.select_all_button.isEnabled()
    assert not view.save_button.isEnabled()
    assert "Generate a grammar" in view.header.text()


def test_set_code_populates_editor_and_enables_buttons(view):
    code = "class LRParser:\n    pass\n"
    view.set_code(code, note="Generated parser")
    assert view.editor.toPlainText() == code
    assert view.copy_button.isEnabled()
    assert view.select_all_button.isEnabled()
    assert view.save_button.isEnabled()
    assert view.header.text() == "Generated parser"


def test_set_code_without_note_uses_default_header(view):
    view.set_code("x = 1\n")
    assert "Generated parser" in view.header.text()


def test_clear_resets_view(view):
    view.set_code("x = 1\n")
    view.clear()
    assert view.editor.toPlainText() == ""
    assert not view.copy_button.isEnabled()
    assert "Generate a grammar" in view.header.text()


def test_highlighter_is_bound_to_editor_document(view):
    assert view.highlighter.document() is view.editor.document()


def test_line_number_gutter_has_width(view):
    assert view.editor.line_number_area_width() > 0


def test_renders_without_error(app, view):
    view.set_code("def parse(self, tokens):\n    return True\n")
    view.resize(600, 400)
    view.show()
    app.processEvents()
    pixmap = QPixmap(view.size())
    view.render(pixmap)
    assert not pixmap.isNull()