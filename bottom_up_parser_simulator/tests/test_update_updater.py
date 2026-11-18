"""Tests for the standalone updater process logic."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from core.update import updater


def _make_zip(zip_path: Path, files: dict) -> Path:
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
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
    return install


def test_wait_for_process_exit_dead_pid(tmp_path):
    # A very high pid is effectively guaranteed not to exist.
    assert updater.wait_for_process_exit(999999, timeout=1.0) is True


def test_wait_for_process_exit_timeout(tmp_path):
    # Waiting on the current (alive) process should time out.
    assert updater.wait_for_process_exit(os.getpid(), timeout=0.2, poll=0.05) is False


def test_pid_alive_current():
    assert updater._pid_alive(os.getpid()) is True
    assert updater._pid_alive(999999) is False


def test_run_update_applies_and_relaunches(tmp_path, monkeypatch):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new"})

    launched = []
    monkeypatch.setattr(
        updater.subprocess, "Popen", lambda *a, **k: launched.append(a) or object()
    )

    code = updater.run_update(package, install, app_exe=str(tmp_path / "app.exe"))

    assert code == 0
    assert (install / "app.exe").read_bytes() == b"new"
    assert launched, "application should be relaunched"


def test_run_update_no_relaunch(tmp_path, monkeypatch):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new"})

    launched = []
    monkeypatch.setattr(
        updater.subprocess, "Popen", lambda *a, **k: launched.append(a) or object()
    )

    code = updater.run_update(package, install, app_exe="x", relaunch=False)

    assert code == 0
    assert launched == []


def test_run_update_failure_returns_nonzero(tmp_path):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    code = updater.run_update(bad, install, app_exe=None, relaunch=False)
    assert code == 1
    assert (install / "app.exe").read_bytes() == b"old"


def test_main_applies_update(tmp_path, monkeypatch):
    install = _make_install_dir(tmp_path, {"app.exe": b"old"})
    package = _make_zip(tmp_path / "update.zip", {"app.exe": b"new"})
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: object())

    code = updater.main(
        [
            "--package",
            str(package),
            "--install-dir",
            str(install),
            "--no-relaunch",
        ]
    )
    assert code == 0
    assert (install / "app.exe").read_bytes() == b"new"