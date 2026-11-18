"""Tests for expanded grammar display (to_expanded_text + GrammarReferencePane)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from core.comparison import compare_parsers
from core.engine import analyze
from core.grammar_parser import parse_grammar
from core.topdown import analyze_topdown
from gui.grammar_reference import GrammarReferencePane
from models.grammar import Grammar

EXPR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"
SAMPLE = "S -> SC | C\nC -> move A | turn\nA -> inspect | spray | water"
LR_TYPES = ["Shift Reduce", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


# ----------------------------------------------------------------------
# Grammar.to_expanded_text
# ----------------------------------------------------------------------
def test_expanded_one_production_per_line():
    g = parse_grammar(SAMPLE)
    text = g.to_expanded_text()
    assert "|" not in text
    lines = text.splitlines()
    # ``SC`` is split into two symbols (S C) by the grammar parser, so the
    # expanded form shows them space-separated.
    assert "S -> S C" in lines
    assert "S -> C" in lines
    assert "C -> move A" in lines
    assert "C -> turn" in lines
    assert "A -> inspect" in lines
    assert "A -> spray" in lines
    assert "A -> water" in lines


def test_expanded_blank_line_between_nonterminals():
    g = parse_grammar(SAMPLE)
    blocks = g.to_expanded_text().split("\n\n")
    assert len(blocks) == 3  # S, C, A


def test_expanded_preserves_declaration_order():
    g = parse_grammar(SAMPLE)
    lines = [ln for ln in g.to_expanded_text().splitlines() if ln]
    # First S productions, then C, then A.
    assert lines[0].startswith("S ")
    assert any(ln.startswith("C ") for ln in lines)
    assert any(ln.startswith("A ") for ln in lines)


def test_expanded_aligns_arrow():
    g = Grammar(start_symbol="S")
    g.add_production("S", ["a"])
    g.add_production("Long", ["b"])
    lines = g.to_expanded_text().splitlines()
    assert lines[0] == "S    -> a"  # "S".ljust(4)
    assert lines[2] == "Long -> b"


def test_expanded_renders_epsilon():
    g = Grammar(start_symbol="S")
    g.add_production("S", ["a"])
    g.add_production("S", [])
    text = g.to_expanded_text()
    assert "S -> a" in text
    assert "S -> ε" in text


def test_expanded_empty_grammar():
    assert Grammar(start_symbol="S").to_expanded_text() == ""


# ----------------------------------------------------------------------
# GrammarReferencePane
# ----------------------------------------------------------------------
def test_pane_set_from_grammar(app):
    g = parse_grammar(SAMPLE)
    pane = GrammarReferencePane()
    pane.set_from_grammar(g)
    assert pane.view.toPlainText() == g.to_expanded_text()
    pane.deleteLater()


def test_pane_set_from_grammar_none_clears(app):
    pane = GrammarReferencePane()
    pane.set_from_grammar(None)
    assert pane.view.toPlainText() == ""
    pane.deleteLater()


def test_pane_set_grammar_raw_text(app):
    pane = GrammarReferencePane()
    pane.set_grammar("S -> a | b")
    assert pane.view.toPlainText() == "S -> a | b"
    pane.deleteLater()


def test_lr_pane_shows_augmented_grammar(app):
    for parser_type in LR_TYPES:
        analysis = analyze(EXPR, parser_type)
        pane = GrammarReferencePane()
        pane.set_from_analysis(analysis)
        text = pane.view.toPlainText()
        assert text.splitlines()[0].startswith("S' -> E"), parser_type
        assert "|" not in text
        pane.deleteLater()


def test_lr_pane_caption_is_augmented(app):
    pane = GrammarReferencePane()
    pane.set_from_analysis(analyze(EXPR, "SLR(1)"))
    assert pane.caption.text() == "Augmented Grammar Used by Parser"
    pane.deleteLater()


def test_topdown_pane_caption_without_transforms(app):
    pane = GrammarReferencePane()
    pane.set_from_analysis(analyze_topdown(EXPR, "LL(1)"))
    assert pane.caption.text() == "Grammar Used by Parser"
    pane.deleteLater()


def test_topdown_pane_caption_with_transforms(app):
    # Left-recursive expression grammar -> remove left recursion -> transformed.
    result = analyze_topdown(EXPR, "LL(1)", remove_left_recursion=True)
    pane = GrammarReferencePane()
    pane.set_from_analysis(result)
    assert pane.caption.text() == "Transformed Grammar"
    assert "|" not in pane.view.toPlainText()
    pane.deleteLater()


def test_non_lr_pane_shows_original_grammar(app):
    result = analyze_topdown(EXPR, "LL(1)")
    pane = GrammarReferencePane()
    pane.set_from_analysis(result)
    text = pane.view.toPlainText()
    assert "S'" not in text
    assert "E -> E + T" in text
    assert "|" not in text
    pane.deleteLater()


def test_lr_states_view_uses_grammar_pane(app):
    from gui.lr_states_view import LRStatesView

    view = LRStatesView()
    view.update_from(analyze(EXPR, "SLR(1)"))
    assert hasattr(view, "grammar")
    assert view.grammar.view.toPlainText().splitlines()[0].startswith("S' -> E")
    view.deleteLater()


def test_first_follow_pane_shows_original_grammar(app):
    # FIRST/FOLLOW are computed on the original grammar, so the reference pane
    # shows it without the augmented S' production.
    from gui.first_follow_view import FirstFollowView

    view = FirstFollowView()
    view.update_from(analyze(EXPR, "SLR(1)"))
    text = view.grammar.view.toPlainText()
    assert "S'" not in text
    assert "E -> E + T" in text
    assert "|" not in text
    view.deleteLater()


def test_comparison_report_has_grammar(app):
    report = compare_parsers(EXPR)
    assert report.grammar is not None
    pane = GrammarReferencePane()
    pane.set_from_grammar(report.grammar, caption="Original Grammar")
    text = pane.view.toPlainText()
    assert "E -> E + T" in text
    assert "|" not in text
    assert pane.caption.text() == "Original Grammar"
    pane.deleteLater()


# ----------------------------------------------------------------------
# Grammar version separation (original vs. transformed vs. augmented)
# ----------------------------------------------------------------------
def test_lr_analysis_keeps_original():
    # LR parsers analyze the grammar as provided: original == used grammar.
    analysis = analyze(EXPR, "SLR(1)")
    assert analysis.original is not None
    assert analysis.original is analysis.grammar
    assert analysis.transforms == []


def test_topdown_keeps_original_separate_from_transformed():
    result = analyze_topdown(EXPR, "LL(1)", remove_left_recursion=True)
    assert result.original is not None
    # The original still has left recursion; the used (transformed) one does not.
    from core.grammar_transform import has_left_recursion

    assert has_left_recursion(result.original) is True
    assert has_left_recursion(result.grammar) is False
    assert result.original is not result.grammar


def test_editor_preview_is_expanded(app):
    from gui.grammar_editor import GrammarEditor

    editor = GrammarEditor()
    editor.set_grammar_variants({"Original": "S -> a | b\nA -> c"})
    text = editor.preview.toPlainText()
    assert "|" not in text
    assert "S -> a" in text
    assert "S -> b" in text
    assert "A -> c" in text
    editor.deleteLater()