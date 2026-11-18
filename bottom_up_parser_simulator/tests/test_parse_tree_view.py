"""Tests for the enhanced Parse Tree view (text + graph + inspection)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtGui import QPixmap, QTextCursor
from PyQt6.QtWidgets import QApplication

from core.parse_tree import make_internal, make_leaf
from gui.parse_tree_view import ParseTreeView

# S -> A B ; A -> a ; B -> b ; plus a unary chain U -> V -> w for collapse tests.


def _sample_tree():
    a = make_internal("A", [make_leaf("a")])
    b = make_internal("B", [make_leaf("b")])
    return make_internal("S", [a, b])


def _unary_tree():
    # U -> V -> w  (single-child chain that collapse should reduce to 'w').
    w = make_leaf("w")
    v = make_internal("V", [w])
    return make_internal("U", [v])


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture()
def view(app):
    v = ParseTreeView()
    v.resize(1200, 700)
    v.show_tree(_sample_tree())
    v.show()
    app.processEvents()
    yield v
    v.deleteLater()


def test_text_uses_unicode_box_drawing(view):
    text = view.text_view.toPlainText()
    assert any(ch in text for ch in ("├──", "└──", "│"))
    # Root symbol present.
    assert "S" in text


def test_text_block_keys_match_visible_nodes(view):
    assert len(view._text_block_keys) == len(view._visible_keys)
    assert len(view._visible_keys) == 5  # S, A, a, B, b


def test_select_node_updates_inspection(view):
    # Pick a non-root, non-leaf node (A) and select it.
    a_key = None
    for key, node in view._node_by_key.items():
        if node.symbol == "A" and not node.is_leaf():
            a_key = key
            break
    assert a_key is not None
    view._select_key(a_key)
    detail = view.detail.toPlainText()
    assert "Production:" in detail
    assert "A → a" in detail
    assert "Derivation" in detail


def test_graph_node_selection_updates_inspection(view):
    key = next(iter(view._node_by_key))
    view._on_graph_node_selected(key)
    assert view._current_key == key
    assert view.detail.toPlainText() != ""


def test_selected_subtree_highlighting(view):
    a_key = None
    for key, node in view._node_by_key.items():
        if node.symbol == "A" and not node.is_leaf():
            a_key = key
            break
    view._select_key(a_key)
    subtree = view._selected_subtree()
    # A's subtree = {A, a} (both visible).
    assert a_key in subtree
    assert len(subtree) == 2


def test_collapse_single_child_reduces_nodes(app):
    v = ParseTreeView()
    v.show_tree(_unary_tree())
    full = len(v._visible_keys)
    assert full == 3  # U, V, w
    v.collapse_cb.setChecked(True)
    app.processEvents()
    # Collapsed: only the terminal 'w' remains reachable.
    assert len(v._visible_keys) < full
    assert "w" in [n.symbol for n in v._node_by_key.values()]
    v.deleteLater()


def test_manual_fold_hides_children(view):
    root_key = id(view._root)
    full = len(view._visible_keys)
    view._folded.add(root_key)
    view._render()
    # Only the root remains visible when its children are folded.
    assert len(view._visible_keys) == 1
    view._folded.discard(root_key)
    view._render()
    assert len(view._visible_keys) == full


def test_clear_resets(view):
    view.clear()
    assert view._visible_keys == set()
    assert view._text_block_keys == []
    assert view._node_by_key == {}


def test_export_png(view, tmp_path):
    out = tmp_path / "tree.png"
    view.canvas.render_to_file(str(out), "png")
    assert out.exists() and out.stat().st_size > 0


def test_export_svg(view, tmp_path):
    out = tmp_path / "tree.svg"
    view.canvas.render_to_file(str(out), "svg")
    assert out.exists() and out.stat().st_size > 0


def test_export_pdf(view, tmp_path):
    out = tmp_path / "tree.pdf"
    view.canvas.render_to_file(str(out), "pdf")
    assert out.exists() and out.stat().st_size > 0


def test_canvas_node_id_at(view):
    from PyQt6.QtCore import QPoint

    root_item = view.canvas._items_by_id[id(view._root)]
    viewport_pt = view.canvas.mapFromScene(root_item.scenePos())
    assert view.canvas.node_id_at(viewport_pt) == id(view._root)
    # A point far away from any node maps to nothing.
    assert view.canvas.node_id_at(QPoint(1, 1)) in (None,)


def test_graph_double_click_folds(view):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    def root_viewport_point():
        root_item = view.canvas._items_by_id[id(view._root)]
        return view.canvas.mapFromScene(root_item.scenePos())

    full = len(view._visible_keys)
    QTest.mouseDClick(
        view.canvas.viewport(), Qt.MouseButton.LeftButton, pos=root_viewport_point()
    )
    # Folding the root hides everything below it.
    assert len(view._visible_keys) == 1
    # Unfold again to restore (recompute the point; re-render re-centred view).
    QTest.mouseDClick(
        view.canvas.viewport(), Qt.MouseButton.LeftButton, pos=root_viewport_point()
    )
    assert len(view._visible_keys) == full


# ----------------------------------------------------------------------
# Additional coverage: initial state, messages, header, text cursor, fold
# edge cases, and a render smoke test.
# ----------------------------------------------------------------------
def test_initial_state(app):
    v = ParseTreeView()
    assert "Run a simulation" in v.header.text()
    assert v.text_view.toPlainText() == ""
    v.deleteLater()


def test_show_message_sets_error_state(app):
    v = ParseTreeView()
    v.show_tree(_sample_tree())
    v.show_message("Parse error at token 3")
    assert v.text_view.toPlainText() == "Parse error at token 3"
    assert v.header.text() == "Parse error at token 3"
    assert len(v.canvas._items_by_id) == 0
    v.deleteLater()


def test_header_reports_node_count_and_depth(view):
    from core.parse_tree import count_nodes

    n = count_nodes(view._root)
    assert f"{n} nodes" in view.header.text()
    assert "depth" in view.header.text()


def test_text_cursor_selects_row(app, view):
    cursor = view.text_view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.movePosition(QTextCursor.MoveOperation.Down)
    view.text_view.setTextCursor(cursor)
    app.processEvents()
    assert view._current_key == id(view._root.children[0])


def test_graph_signal_selects_node(view):
    key = id(view._root)
    view.canvas.node_selected.emit(key)
    assert view._current_key == key


def test_fold_leaf_is_rejected(view):
    leaf = view._root.children[0].children[0]  # 'a' leaf under A
    assert view._toggle_fold(id(leaf)) is False


def test_renders_without_error(app, view):
    pixmap = QPixmap(view.size())
    view.render(pixmap)
    assert not pixmap.isNull()