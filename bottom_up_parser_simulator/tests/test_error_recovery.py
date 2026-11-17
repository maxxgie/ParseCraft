"""Tests for LR error recovery (panic-mode and phrase-level)."""

from __future__ import annotations

import pytest

from core.engine import analyze
from core.error_recovery import RECOVERY_MODES, recover_input

GRAMMAR = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"


@pytest.fixture(scope="module")
def analysis():
    return analyze(GRAMMAR, "SLR(1)")


def _recover(analysis, text, mode):
    return recover_input(analysis.table, analysis.grammar, text, mode)


def test_valid_input_has_no_events(analysis):
    report = _recover(analysis, "id + id", "panic-mode")
    assert report.accepted
    assert report.events == []


@pytest.mark.parametrize("mode", RECOVERY_MODES)
def test_extra_token_is_recovered(analysis, mode):
    report = _recover(analysis, "id id", mode)
    assert report.accepted
    assert report.recovered
    assert len(report.events) >= 1


def test_panic_rejects_missing_operand(analysis):
    report = _recover(analysis, "id +", "panic-mode")
    assert report.accepted is False


def test_panic_deletes_stray_token(analysis):
    report = _recover(analysis, "id + ) id", "panic-mode")
    assert report.accepted
    assert any(e.deleted >= 1 for e in report.events)


def test_phrase_inserts_missing_operand(analysis):
    report = _recover(analysis, "id +", "phrase-level")
    assert report.accepted
    assert any(e.inserted for e in report.events)


def test_phrase_inserts_missing_paren(analysis):
    report = _recover(analysis, "( id + id", "phrase-level")
    assert report.accepted
    assert any(")" in e.inserted for e in report.events)


def test_report_text_mentions_mode(analysis):
    report = _recover(analysis, "id id", "phrase-level")
    text = report.report_text()
    assert "phrase-level" in text
    assert "Recovery actions" in text


def test_unknown_mode_raises(analysis):
    with pytest.raises(ValueError):
        _recover(analysis, "id", "bogus-mode")


def test_events_have_expected_tokens(analysis):
    report = _recover(analysis, "id id", "panic-mode")
    assert report.events
    assert report.events[0].expected