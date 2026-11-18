"""Tests for update installation (ZIP overlay, rollback, pending updates)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from core.update import installer


def _make_zip(zip_path: Path, files: dict) -> Path:
    """Create a ZIP with the given ``{relative_name: bytes}`` mapping."""
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return zip_path


def _make_install_dir(root: Path, files: dict) -> Path:
    install = root / "install"
    install.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = install / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return install


def test_apply_zip_overlays_files(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old", "keep.txt": "keep"})
    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new", "added.txt": "hi"})

    result = installer.apply_zip_update(package, install)

    assert result.success is True
    assert (install / "app.exe").read_bytes() == b"new"
    assert (install / "added.txt").read_text() == "hi"
    assert (install / "keep.txt").read_text() == "keep"  # untouched file preserved


def test_apply_zip_creates_backup(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new"})

    result = installer.apply_zip_update(package, install, backup=True)

    assert result.success is True
    assert result.backup_dir is not None
    assert result.backup_dir.exists()
    assert (result.backup_dir / "app.exe").read_bytes() == b"old"


def test_apply_zip_single_top_level_folder(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    # ZIP with a single top-level folder wrapping the payload.
    package = _make_zip(tmp_path / "update.zip", {"payload/app.exe": b"new"})

    result = installer.apply_zip_update(package, install)

    assert result.success is True
    assert (install / "app.exe").read_bytes() == b"new"


def test_apply_zip_rolls_back_on_bad_zip(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is not a zip file")

    result = installer.apply_zip_update(bad, install)

    assert result.success is False
    assert result.error is not None
    # Original install is intact after rollback.
    assert (install / "app.exe").read_bytes() == b"old"


def test_apply_zip_missing_package(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    result = installer.apply_zip_update(tmp_path / "missing.zip", install)
    assert result.success is False
    assert "not found" in (result.error or "").lower()


def test_zip_slip_protection(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    # Craft a zip whose entry tries to escape the install dir.
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../escape.txt", "pwned")

    result = installer.apply_zip_update(evil, install)

    assert result.success is False
    assert not (tmp_path / "escape.txt").exists()


def test_pending_update_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "get_app_data_dir", lambda: tmp_path)
    manifest = {"version": "1.2.0", "package_type": "zip"}
    package = tmp_path / "update.zip"
    package.write_bytes(b"zip")

    marker = installer.write_pending_update(manifest, package)
    assert marker.exists()

    pending = installer.read_pending_update()
    assert pending is not None
    assert pending.manifest["version"] == "1.2.0"
    assert pending.package_path == str(package)

    installer.clear_pending_update()
    assert installer.read_pending_update() is None


def test_apply_pending_none_when_no_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "get_app_data_dir", lambda: tmp_path)
    assert installer.apply_pending_update() is None


def test_apply_pending_applies_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "get_app_data_dir", lambda: tmp_path)
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    monkeypatch.setattr(installer, "get_install_dir", lambda: install)

    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new"})
    installer.write_pending_update({"version": "1.2.0", "package_type": "zip"}, package)

    result = installer.apply_pending_update()

    assert result is not None and result.success is True
    assert (install / "app.exe").read_bytes() == b"new"
    # Marker cleared regardless of outcome.
    assert installer.read_pending_update() is None


def test_launch_updater_builds_command(tmp_path, monkeypatch):
    package = tmp_path / "pkg.zip"
    package.write_bytes(b"zip")
    captured = {}

    class DummyPopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

    monkeypatch.setattr(installer.subprocess, "Popen", DummyPopen)

    popen = installer.launch_updater(package, tmp_path, "app.exe", pid=123)

    assert isinstance(popen, DummyPopen)
    cmd = captured["cmd"]
    assert "--package" in cmd and str(package) in cmd
    assert "--pid" in cmd and "123" in cmd
    assert "--app-exe" in cmd and "app.exe" in cmd
    # Source mode runs the updater module via the current interpreter.
    assert any("core.update.updater" in str(part) for part in cmd)


def test_launch_updater_missing_package(tmp_path):
    with pytest.raises(installer.InstallError):
        installer.launch_updater(tmp_path / "missing.zip", tmp_path, "app.exe")