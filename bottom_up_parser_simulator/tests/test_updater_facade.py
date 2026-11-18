"""Tests for the core/updater.py facade (check_for_updates)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.preferences import Preferences
from core.update.history import UpdateHistoryStore
from core.update.manager import UpdateManager
from core.updater import (
    STATUS_ERROR,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
    UpdateCheckResult,
    check_for_updates,
)
from core.version import APP_VERSION


def _write_manifest(path: Path, version: str, **overrides) -> Path:
    data = {
        "app_name": "ParseCraft",
        "latest_version": version,
        "build": "101",
        "release_date": "2026-12-01",
        "download_url": "https://github.com/maxxgie/ParseCraft/releases/download/v"
        + version
        + "/ParseCraft-"
        + version
        + "-Setup.exe",
        "sha256": "",
        "release_notes": ["- New feature", "- Bug fix"],
        "package_type": "installer",
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _manager(tmp_path) -> UpdateManager:
    return UpdateManager(
        Preferences(tmp_path / "preferences.json"),
        UpdateHistoryStore(tmp_path / "update_history.json"),
    )


def test_up_to_date(tmp_path):
    manifest_path = _write_manifest(tmp_path / "manifest.json", APP_VERSION)
    mgr = _manager(tmp_path)
    result = check_for_updates(mgr, url=manifest_path.as_uri())

    assert isinstance(result, UpdateCheckResult)
    assert result.status == STATUS_UP_TO_DATE
    assert result.update_available is False
    assert result.latest_version == APP_VERSION
    assert "up to date" in result.message.lower()


def test_update_available(tmp_path):
    manifest_path = _write_manifest(tmp_path / "manifest.json", "1.1.0")
    mgr = _manager(tmp_path)
    result = check_for_updates(mgr, url=manifest_path.as_uri())

    assert result.status == STATUS_UPDATE_AVAILABLE
    assert result.update_available is True
    assert result.latest_version == "1.1.0"
    assert result.current_version == APP_VERSION
    assert result.manifest is not None
    assert result.manifest.download_url.endswith("ParseCraft-1.1.0-Setup.exe")
    assert "1.0.0 -> 1.1.0" in result.message
    # History recorded a check event.
    assert any(e.event == "check" for e in mgr.get_history())


def test_error_on_unreachable(tmp_path):
    mgr = _manager(tmp_path)
    result = check_for_updates(mgr, url=(tmp_path / "missing.json").as_uri())

    assert result.status == STATUS_ERROR
    assert result.update_available is False
    assert result.error
    assert "failed" in result.message.lower()


def test_error_on_invalid_manifest(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    mgr = _manager(tmp_path)
    result = check_for_updates(mgr, url=bad.as_uri())
    assert result.status == STATUS_ERROR


def test_uses_user_setting_url(tmp_path, monkeypatch):
    manifest_path = _write_manifest(tmp_path / "manifest.json", "1.1.0")
    mgr = _manager(tmp_path)
    mgr.update_settings({"manifest_url": manifest_path.as_uri()})
    # Ensure the env var would point elsewhere (user setting must win).
    monkeypatch.setenv("BUP_UPDATES_URL", (tmp_path / "other.json").as_uri())

    result = check_for_updates(mgr)
    assert result.status == STATUS_UPDATE_AVAILABLE


def test_result_message_constants(tmp_path):
    result = UpdateCheckResult(status=STATUS_ERROR, current_version="1.0.0", error="boom")
    assert "boom" in result.message
    assert result.is_update_available is False