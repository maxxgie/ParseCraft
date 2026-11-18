"""Tests for the dedicated update history store (update_history.json)."""

from __future__ import annotations

import json

from core.update.history import UpdateHistoryStore, get_history_path


def test_empty_history(tmp_path):
    store = UpdateHistoryStore(tmp_path / "update_history.json")
    assert store.entries() == []


def test_record_and_order(tmp_path):
    store = UpdateHistoryStore(tmp_path / "update_history.json")
    store.record("check", detail="first")
    store.record("install", version="1.1.0", detail="second", changes=["- a", "- b"])
    store.record("rollback", version="1.1.0", detail="third")

    entries = store.entries()
    assert [e.event for e in entries] == ["rollback", "install", "check"]
    install = entries[1]
    assert install.version == "1.1.0"
    assert install.changes == ["- a", "- b"]


def test_persists_across_instances(tmp_path):
    path = tmp_path / "update_history.json"
    UpdateHistoryStore(path).record("install", version="2.0.0", detail="done")
    reloaded = UpdateHistoryStore(path)
    entries = reloaded.entries()
    assert len(entries) == 1
    assert entries[0].version == "2.0.0"


def test_writes_update_history_json_file(tmp_path):
    path = tmp_path / "update_history.json"
    UpdateHistoryStore(path).record("install", version="1.1.0", detail="x")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["version"] == "1.1.0"
    assert data[0]["event"] == "install"


def test_corrupt_file_recovers(tmp_path):
    path = tmp_path / "update_history.json"
    path.write_text("not json", encoding="utf-8")
    store = UpdateHistoryStore(path)
    assert store.entries() == []


def test_clear(tmp_path):
    store = UpdateHistoryStore(tmp_path / "update_history.json")
    store.record("check")
    store.clear()
    assert store.entries() == []


def test_get_history_path_default():
    path = get_history_path()
    assert path.name == "update_history.json"