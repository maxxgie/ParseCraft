"""Tests for per-user path resolution."""

from __future__ import annotations

from pathlib import Path

from core import paths


def test_is_frozen_false_in_source():
    assert paths.is_frozen() is False


def test_app_data_dir_is_project_data_in_source():
    data_dir = paths.get_app_data_dir()
    assert data_dir.name == "data"
    assert data_dir.exists()
    assert data_dir.is_dir()


def test_logs_dir_exists():
    logs = paths.get_logs_dir()
    assert logs.exists() and logs.is_dir()
    assert logs.name == "logs"


def test_cache_dir_exists():
    cache = paths.get_cache_dir()
    assert cache.exists() and cache.is_dir()
    assert cache.name == "downloads"


def test_install_dir_is_project_root_in_source():
    assert paths.get_install_dir() == paths.PROJECT_ROOT


def test_executable_path_is_sys_executable():
    import sys

    assert paths.get_executable_path() == Path(sys.executable)


def test_is_writable_dir_true(tmp_path):
    assert paths.is_writable_dir(tmp_path) is True


def test_ensure_runtime_dirs_returns_dir():
    result = paths.ensure_runtime_dirs()
    assert result is not None and result.is_dir()