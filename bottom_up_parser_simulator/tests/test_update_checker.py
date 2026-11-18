"""Tests for update manifest fetching and comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.update.checker import (
    CheckError,
    check_for_update,
    fetch_manifest,
    resolve_manifest_url,
)
from core.version import DEFAULT_MANIFEST_URL


def _write_manifest(path: Path, **overrides) -> Path:
    data = {
        "version": "2.0.0",
        "release_date": "2026-11-18",
        "release_notes": "notes",
        "download_url": "https://example.com/app.zip",
        "sha256": "b" * 64,
        "size": 10,
        "min_version": "1.0.0",
        "package_type": "zip",
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_fetch_manifest_file_url(tmp_path):
    path = _write_manifest(tmp_path / "update.json")
    manifest = fetch_manifest(path.as_uri())
    assert manifest.version == "2.0.0"


def test_check_for_update_detects_newer(tmp_path):
    path = _write_manifest(tmp_path / "update.json")
    manifest = check_for_update("1.0.0", url=path.as_uri())
    assert manifest is not None
    assert manifest.version == "2.0.0"


def test_check_for_update_none_when_current(tmp_path):
    path = _write_manifest(tmp_path / "update.json")
    assert check_for_update("2.0.0", url=path.as_uri()) is None


def test_check_for_update_none_when_ahead(tmp_path):
    path = _write_manifest(tmp_path / "update.json")
    assert check_for_update("3.0.0", url=path.as_uri()) is None


def test_check_for_update_skips_incompatible(tmp_path):
    path = _write_manifest(tmp_path / "update.json", min_version="2.5.0")
    # 1.0.0 is newer than nothing but below min_version 2.5.0 -> skipped.
    assert check_for_update("1.0.0", url=path.as_uri()) is None


def test_fetch_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(CheckError):
        fetch_manifest(path.as_uri())


def test_fetch_missing_file_raises(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(CheckError):
        fetch_manifest(missing.as_uri())


def test_resolve_manifest_url_explicit():
    assert resolve_manifest_url("https://x/y.json") == "https://x/y.json"


def test_resolve_manifest_url_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BUP_UPDATES_URL", "https://env/url.json")
    assert resolve_manifest_url(None) == "https://env/url.json"


def test_resolve_manifest_url_default(monkeypatch):
    monkeypatch.delenv("BUP_UPDATES_URL", raising=False)
    assert resolve_manifest_url(None) == DEFAULT_MANIFEST_URL