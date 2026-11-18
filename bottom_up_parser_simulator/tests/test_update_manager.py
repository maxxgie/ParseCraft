"""Tests for the high-level UpdateManager facade."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from core.preferences import Preferences
from core.update import installer, manager as manager_mod
from core.update.history import UpdateHistoryStore
from core.update.manager import UpdateManager


def _make_package(path: Path, files: dict) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def _write_manifest(path: Path, package: Path, **overrides) -> Path:
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    data = {
        "version": "1.2.0",
        "release_date": "2026-11-18",
        "release_notes": "- Added automatic updates\n- Fixed export crash",
        "download_url": package.as_uri(),
        "sha256": digest,
        "size": package.stat().st_size,
        "min_version": "1.0.0",
        "package_type": "zip",
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _manager(tmp_path) -> UpdateManager:
    return UpdateManager(
        Preferences(tmp_path / "preferences.json"),
        UpdateHistoryStore(tmp_path / "update_history.json"),
    )


def test_current_version():
    mgr = _manager(Path("."))
    from core.version import APP_VERSION

    assert mgr.current_version == APP_VERSION


def test_get_and_update_settings(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr.get_settings()["auto_check"] is True
    mgr.update_settings({"auto_download": True})
    assert mgr.get_settings()["auto_download"] is True


def test_should_check(tmp_path):
    mgr = _manager(tmp_path)
    assert mgr.should_check() is True
    mgr.update_settings({"auto_check": False})
    assert mgr.should_check() is False
    mgr.update_settings({"auto_check": True, "check_on_startup": False})
    assert mgr.should_check() is False


def test_check_returns_manifest_when_newer(tmp_path):
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package)

    mgr = _manager(tmp_path)
    manifest = mgr.check(url=manifest_path.as_uri())

    assert manifest is not None
    assert manifest.version == "1.2.0"
    # A check event was recorded.
    events = [e.event for e in mgr.get_history()]
    assert "check" in events


def test_check_none_when_up_to_date(tmp_path):
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package, version="0.9.0")

    mgr = _manager(tmp_path)
    assert mgr.check(url=manifest_path.as_uri()) is None


def test_check_raises_on_unreachable(tmp_path):
    mgr = _manager(tmp_path)
    from core.update.checker import CheckError

    with pytest.raises(CheckError):
        mgr.check(url=(tmp_path / "missing.json").as_uri())


def test_download_and_verify(tmp_path):
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package)
    mgr = _manager(tmp_path)

    # Redirect cache into tmp.
    import core.update.manager as mm

    original = mm.get_cache_dir
    mm.get_cache_dir = lambda: tmp_path / "cache"
    try:
        manifest = mgr.check(url=manifest_path.as_uri())
        path = mgr.download(manifest)
    finally:
        mm.get_cache_dir = original

    assert path.exists()
    assert path.read_bytes() == package.read_bytes()
    assert any(e.event == "download" for e in mgr.get_history())


def test_download_detects_corruption(tmp_path):
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package)
    # Corrupt the source so the served bytes won't match the manifest digest.
    package.write_bytes(b"corrupted-after-hashing")
    mgr = _manager(tmp_path)

    import core.update.manager as mm

    original = mm.get_cache_dir
    mm.get_cache_dir = lambda: tmp_path / "cache"
    try:
        manifest = mgr.check(url=manifest_path.as_uri())
        from core.update.verifier import VerificationError

        with pytest.raises(VerificationError):
            mgr.download(manifest)
    finally:
        mm.get_cache_dir = original


def test_install_now_overlays(tmp_path, monkeypatch):
    install = tmp_path / "install"
    install.mkdir()
    (install / "app.exe").write_bytes(b"old")

    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package)
    mgr = _manager(tmp_path)
    manifest = mgr.check(url=manifest_path.as_uri())

    import core.update.installer as inst

    monkeypatch.setattr(inst, "get_install_dir", lambda: install)

    result = mgr.install_now(package, manifest)
    assert result.success is True
    assert (install / "app.exe").read_bytes() == b"new"
    assert any(e.event == "install" for e in mgr.get_history())


def test_schedule_for_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "get_app_data_dir", lambda: tmp_path)
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package)
    mgr = _manager(tmp_path)
    manifest = mgr.check(url=manifest_path.as_uri())

    marker = mgr.schedule_for_restart(package, manifest)
    assert marker.exists()
    pending = installer.read_pending_update()
    assert pending is not None and pending.manifest["version"] == "1.2.0"


def test_check_and_download_no_update(tmp_path):
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})
    manifest_path = _write_manifest(tmp_path / "update.json", package, version="0.0.1")
    mgr = _manager(tmp_path)
    # Route the internal check() through the local manifest (no network).
    mgr.update_settings({"manifest_url": manifest_path.as_uri()})
    manifest, path = mgr.check_and_download()
    assert manifest is None and path is None


def test_install_now_frozen_uses_updater(tmp_path, monkeypatch):
    from core.update.manifest import ReleaseManifest

    mgr = _manager(tmp_path)
    package = _make_package(tmp_path / "pkg.zip", {"app.exe": b"new"})

    import core.update.manager as mm

    monkeypatch.setattr(mm, "is_frozen", lambda: True)
    calls = {}
    monkeypatch.setattr(
        mm, "launch_updater", lambda *a, **k: calls.setdefault("args", (a, k))
    )

    manifest = ReleaseManifest(version="1.2.0", package_type="zip")
    result = mgr.install_now(package, manifest)

    assert result.success is True
    assert result.requires_restart is True
    assert "args" in calls
    assert any(e.event == "install" for e in mgr.get_history())