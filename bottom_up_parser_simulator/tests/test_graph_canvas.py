"""Tests for the reusable graph canvas (rendering, highlight, export)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from gui.graph_canvas import GraphCanvas, GraphEdge, GraphNode


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def canvas(app):
    c = GraphCanvas()
    c.resize(600, 400)
    c.render(
        [
            GraphNode(id=1, label="S", x=0.0, y=0.0, kind="root"),
            GraphNode(id=2, label="a", x=-50.0, y=80.0, kind="terminal"),
            GraphNode(id=3, label="b", x=50.0, y=80.0, kind="terminal"),
        ],
        [GraphEdge(src=1, dst=2), GraphEdge(src=1, dst=3)],
    )
    app.processEvents()
    yield c
    c.deleteLater()


def test_render_creates_items(canvas):
    assert len(canvas._items_by_id) == 3


def test_node_selected_signal(canvas):
    received = []
    canvas.node_selected.connect(received.append)
    # Selecting a node item should surface its id through the signal.
    item = canvas._items_by_id[2]
    item.setSelected(True)
    assert 2 in received


def test_set_highlight_marks_subset(canvas):
    canvas.set_highlight({2})
    # The tracked highlight set is updated and the matching item is restyled.
    assert canvas._highlighted == {2}
    assert canvas._items_by_id[2].pen().color().name().lower() == "#2563eb"


def test_render_to_png(canvas, tmp_path):
    out = tmp_path / "graph.png"
    assert canvas.render_to_file(str(out), "png") is True
    assert out.exists() and out.stat().st_size > 0


def test_render_to_svg(canvas, tmp_path):
    out = tmp_path / "graph.svg"
    assert canvas.render_to_file(str(out), "svg") is True
    assert out.exists() and out.stat().st_size > 0


def test_render_to_pdf(canvas, tmp_path):
    out = tmp_path / "graph.pdf"
    assert canvas.render_to_file(str(out), "pdf") is True
    assert out.exists() and out.stat().st_size > 0


def test_empty_scene_export_returns_false(app):
    c = GraphCanvas()
    assert c.render_to_file("unused.png", "png") is False
    c.deleteLater()