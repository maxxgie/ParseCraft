"""Tests for the update package downloader."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest

from core.update.downloader import (
    DownloadCancelled,
    DownloadError,
    download,
    download_to_cache,
    filename_from_url,
)


def _file_url(path: Path) -> str:
    return path.as_uri()


def test_download_file_url(tmp_path):
    src = tmp_path / "source.bin"
    payload = b"update-package-contents" * 1000
    src.write_bytes(payload)

    dest = tmp_path / "out" / "downloaded.bin"
    result = download(_file_url(src), dest)
    assert result == dest
    assert dest.read_bytes() == payload


def test_download_reports_progress(tmp_path):
    src = tmp_path / "source.bin"
    payload = b"x" * (256 * 1024)  # 256 KiB to force multiple chunks
    src.write_bytes(payload)

    progress = []
    dest = tmp_path / "downloaded.bin"
    download(_file_url(src), dest, progress_cb=lambda d, t: progress.append((d, t)))

    assert progress, "progress callback should have been called"
    assert progress[-1][0] == len(payload)
    assert progress[-1][1] == len(payload)


def test_download_cancel_before_start(tmp_path):
    src = tmp_path / "source.bin"
    src.write_bytes(b"data")
    event = threading.Event()
    event.set()  # already cancelled

    with pytest.raises(DownloadCancelled):
        download(_file_url(src), tmp_path / "out.bin", cancel_event=event)
    assert not (tmp_path / "out.bin").exists()


def test_download_missing_source_raises(tmp_path):
    missing = tmp_path / "does_not_exist.bin"
    with pytest.raises(DownloadError):
        download(_file_url(missing), tmp_path / "out.bin")


def test_download_leaves_no_partial_file_on_error(tmp_path):
    missing = tmp_path / "nope.bin"
    dest = tmp_path / "out.bin"
    with pytest.raises(DownloadError):
        download(_file_url(missing), dest)
    assert not dest.exists()
    # No leftover .part files.
    assert list(tmp_path.glob("*.part")) == []


def test_download_to_cache(tmp_path):
    src = tmp_path / "source.bin"
    src.write_bytes(b"abc")
    cache = tmp_path / "cache"
    result = download_to_cache(_file_url(src), "pkg.zip", cache_dir=cache)
    assert result == cache / "pkg.zip"
    assert result.read_bytes() == b"abc"


def test_filename_from_url():
    assert filename_from_url("https://example.com/path/app-1.2.0.zip") == "app-1.2.0.zip"
    assert filename_from_url("https://example.com/") == "update.bin"
    assert filename_from_url("https://example.com/a/b/") == "update.bin"


def test_download_atomic_replace(tmp_path):
    src = tmp_path / "source.bin"
    src.write_bytes(b"new-content")
    dest = tmp_path / "existing.bin"
    dest.write_bytes(b"old-content")
    download(_file_url(src), dest)
    assert dest.read_bytes() == b"new-content"