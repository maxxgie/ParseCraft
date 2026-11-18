"""Tests for the JSON-backed preferences store."""

from __future__ import annotations

import json

from core.preferences import (
    DEFAULT_UPDATE_PREFERENCES,
    Preferences,
    UpdateHistoryEntry,
)


def test_defaults_when_no_file(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    settings = prefs.get_update_preferences()
    assert settings["auto_check"] is True
    assert settings["auto_download"] is False
    assert settings["channel"] == DEFAULT_UPDATE_PREFERENCES["channel"]


def test_set_and_persist_update_preferences(tmp_path):
    path = tmp_path / "preferences.json"
    prefs = Preferences(path)
    prefs.set_update_preferences({"auto_download": True, "channel": "beta"})
    prefs.save()

    reloaded = Preferences(path).load()
    settings = reloaded.get_update_preferences()
    assert settings["auto_download"] is True
    assert settings["channel"] == "beta"
    # Untouched keys keep defaults.
    assert settings["auto_install"] is False


def test_unknown_keys_ignored(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    prefs.set_update_preferences({"nonexistent": 123})
    assert "nonexistent" not in prefs.get_update_preferences()


def test_history_appends_and_orders_newest_first(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    prefs.record_update_event("check", detail="first")
    prefs.record_update_event("download", version="1.1.0", detail="second")
    prefs.record_update_event("install", version="1.1.0", detail="third")

    history = prefs.get_update_history()
    assert len(history) == 3
    assert [e.event for e in history] == ["install", "download", "check"]
    assert history[0].detail == "third"
    assert all(isinstance(e, UpdateHistoryEntry) for e in history)


def test_history_persists_across_instances(tmp_path):
    path = tmp_path / "preferences.json"
    Preferences(path).record_update_event("install", version="2.0.0")
    reloaded = Preferences(path).load()
    history = reloaded.get_update_history()
    assert len(history) == 1
    assert history[0].version == "2.0.0"


def test_corrupt_file_recovers_to_defaults(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    prefs = Preferences(path).load()
    assert prefs.get_update_preferences()["auto_check"] is True


def test_save_writes_valid_json(tmp_path):
    path = tmp_path / "preferences.json"
    prefs = Preferences(path)
    prefs.set_update_preferences({"auto_install": True})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["updates"]["auto_install"] is True


def test_top_level_get_set(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    prefs.set("theme", "dark")
    assert prefs.get("theme") == "dark"
    assert prefs.get("missing", "fallback") == "fallback"