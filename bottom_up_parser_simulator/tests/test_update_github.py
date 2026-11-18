"""Tests for the GitHub Releases update backend configuration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import version as v
from core.update.checker import CheckError, fetch_manifest
from core.update.downloader import DownloadError, download
from core.update.manifest import ReleaseManifest
from core.update.urls import is_secure_url, scheme_of
from core.version import Version as _Version

REPO_ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# Central configuration
# ----------------------------------------------------------------------
def test_default_manifest_url_is_github_raw():
    assert v.DEFAULT_MANIFEST_URL.startswith("https://raw.githubusercontent.com/")
    assert v.DEFAULT_MANIFEST_URL.endswith("/manifest.json")
    assert "maxxgie/ParseCraft" in v.DEFAULT_MANIFEST_URL
    assert "bottom_up_parser_simulator" in v.DEFAULT_MANIFEST_URL


def test_default_manifest_url_exact():
    assert v.DEFAULT_MANIFEST_URL == (
        "https://raw.githubusercontent.com/maxxgie/ParseCraft/main/"
        "bottom_up_parser_simulator/manifest.json"
    )


def test_github_repo_constants():
    assert v.GITHUB_REPO_OWNER == "maxxgie"
    assert v.GITHUB_REPO_NAME == "ParseCraft"
    assert v.GITHUB_REPO == "maxxgie/ParseCraft"


def test_app_name_constant():
    assert v.APP_NAME == "ParseCraft"


# ----------------------------------------------------------------------
# manifest.json (checked into the repo)
# ----------------------------------------------------------------------
def test_repo_manifest_json_parses():
    manifest_file = REPO_ROOT / "manifest.json"
    assert manifest_file.exists()
    manifest = ReleaseManifest.from_json(manifest_file.read_text(encoding="utf-8"))
    assert manifest.app_name == v.APP_NAME
    # The repo manifest advertises the *latest available* version, which the
    # auto-release workflow bumps ahead of the installed APP_VERSION. It must
    # therefore be at least as new as the installed version, not equal.
    latest = _Version.parse(manifest.version)
    installed = _Version.parse(v.APP_VERSION)
    assert (latest.major, latest.minor, latest.patch) >= (
        installed.major,
        installed.minor,
        installed.patch,
    )
    assert isinstance(manifest.release_notes, str) and manifest.release_notes


def test_repo_manifest_uses_github_schema_keys():
    data = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert "app_name" in data
    assert "latest_version" in data
    assert "release_date" in data
    assert "download_url" in data
    assert "release_notes" in data
    assert isinstance(data["release_notes"], list)


def test_repo_manifest_download_url_is_github():
    data = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert data["download_url"].startswith("https://github.com/")
    assert "/releases/download/" in data["download_url"]


# ----------------------------------------------------------------------
# URL resolution priority: user setting > env > default
# ----------------------------------------------------------------------
def test_resolve_priority_user_setting():
    from core.update.checker import resolve_manifest_url

    assert resolve_manifest_url("https://custom/manifest.json") == "https://custom/manifest.json"


def test_resolve_priority_env_over_default(monkeypatch):
    from core.update.checker import resolve_manifest_url

    monkeypatch.setenv("BUP_UPDATES_URL", "https://env/manifest.json")
    assert resolve_manifest_url(None) == "https://env/manifest.json"


def test_resolve_priority_default(monkeypatch):
    from core.update.checker import resolve_manifest_url

    monkeypatch.delenv("BUP_UPDATES_URL", raising=False)
    assert resolve_manifest_url(None) == v.DEFAULT_MANIFEST_URL


def test_manager_uses_user_setting_over_env(tmp_path, monkeypatch):
    from core.preferences import Preferences
    from core.update import manager as manager_mod
    from core.update.history import UpdateHistoryStore
    from core.update.manager import UpdateManager

    captured = {}

    def fake_check(installed, *, url=None, timeout=15.0):
        captured["url"] = url
        return None

    monkeypatch.setattr(manager_mod, "check_for_update", fake_check)
    prefs = Preferences(tmp_path / "preferences.json")
    prefs.set_update_preferences({"manifest_url": "https://user/manifest.json"})
    monkeypatch.setenv("BUP_UPDATES_URL", "https://env/manifest.json")

    mgr = UpdateManager(prefs, UpdateHistoryStore(tmp_path / "update_history.json"))
    mgr.check()
    # User setting must win over the environment variable.
    assert captured["url"] == "https://user/manifest.json"


# ----------------------------------------------------------------------
# HTTPS enforcement
# ----------------------------------------------------------------------
def test_is_secure_url():
    assert is_secure_url("https://example.com/manifest.json") is True
    assert is_secure_url("file:///C:/tmp/manifest.json") is True
    assert is_secure_url("http://example.com/manifest.json") is False
    assert scheme_of("HTTPS://x") == "https"


def test_downloader_rejects_http(tmp_path):
    with pytest.raises(DownloadError):
        download("http://example.com/app.zip", tmp_path / "app.zip")


def test_checker_rejects_http_manifest(tmp_path):
    with pytest.raises(CheckError):
        fetch_manifest("http://example.com/manifest.json")