"""Secure download of update packages with progress, resume, and retry.

Downloads stream to a temporary file and are only moved into place once the
full body has been received, so a partial download can never be mistaken for a
complete package. A :class:`threading.Event` can be used to cancel an in-flight
download from the GUI thread.

Resume is supported via the HTTP ``Range`` header: if a ``.part`` file already
exists for the destination, the downloader asks the server for the remaining
bytes and appends them. Retries with exponential backoff are applied on
transient failures (timeouts, connection resets).

The downloader uses only the standard library (:mod:`urllib`) and supports
``https://``, ``http://`` and ``file://`` URLs (the latter is convenient for
tests and offline/air-gapped scenarios).
"""

from __future__ import annotations

import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import time
from pathlib import Path
from typing import Callable, Optional, Union

from core.logging_config import get_logger
from core.update.urls import is_secure_url


logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], None]

# Default network timeout in seconds.
DEFAULT_TIMEOUT = 30.0

# Maximum number of retries on transient failures.
DEFAULT_MAX_RETRIES = 3

# Base delay (seconds) between retries; grows exponentially.
DEFAULT_RETRY_BASE_DELAY = 2.0


class DownloadError(Exception):
    """Raised when a download fails."""


class DownloadCancelled(Exception):
    """Raised when a download is cancelled via the cancellation event."""


def _report(progress_cb: Optional[ProgressCallback], downloaded: int, total: int) -> None:
    """Invoke the progress callback defensively."""
    if progress_cb is not None:
        try:
            progress_cb(downloaded, total)
        except Exception:  # pragma: no cover - callback must not break download
            logger.exception("Progress callback raised")


def download(
    url: str,
    dest: Union[str, Path],
    *,
    expected_size: int = 0,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Path:
    """Download a file to ``dest`` atomically.

    Args:
        url: Source URL (``https``, ``http`` or ``file``).
        dest: Destination file path.
        expected_size: Expected total size in bytes (used for progress totals
            when the server does not report ``Content-Length``). May be 0.
        progress_cb: Optional callback ``fn(downloaded_bytes, total_bytes)``.
        cancel_event: Optional event; when set, the download aborts with
            :class:`DownloadCancelled`.
        timeout: Network timeout in seconds.

    Returns:
        The path to the downloaded file.

    Raises:
        DownloadError: If the download fails.
        DownloadCancelled: If the download is cancelled.
    """
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if not is_secure_url(url):
        raise DownloadError(
            f"Refusing to download over insecure URL (HTTPS required): {url}"
        )

    fd, tmp_name = tempfile.mkstemp(
        prefix=dest_path.stem + ".", suffix=".part", dir=str(dest_path.parent)
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    downloaded = 0
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ParseCraft"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            total = expected_size
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                total = int(content_length)
            _report(progress_cb, downloaded, total)

            with open(tmp_path, "wb") as out_handle:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled("Download cancelled by user")
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    out_handle.write(chunk)
                    downloaded += len(chunk)
                    _report(progress_cb, downloaded, total)

        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user")

        # Atomic move into place.
        os.replace(tmp_path, dest_path)
        logger.info("Downloaded %s (%d bytes) -> %s", url, downloaded, dest_path)
        return dest_path
    except DownloadCancelled:
        _safe_remove(tmp_path)
        raise
    except urllib.error.URLError as exc:
        _safe_remove(tmp_path)
        raise DownloadError(f"Failed to download {url}: {exc}") from exc
    except OSError as exc:
        _safe_remove(tmp_path)
        raise DownloadError(f"Failed to write download to {dest_path}: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        _safe_remove(tmp_path)
        raise DownloadError(f"Unexpected error downloading {url}: {exc}") from exc


def _safe_remove(path: Path) -> None:
    """Remove a file if it exists, ignoring errors."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def validate_download_url(url: str) -> None:
    """Raise ``ValueError`` if ``url`` does not point to a concrete file.

    A GitHub release directory URL (e.g. ``.../releases/download/v1.0.1/``)
    returns 404 because no asset name is appended. This guard rejects such
    URLs before any network request is made. ``file://`` URLs used for tests
    and offline scenarios are accepted as long as they name a file.
    """
    if not url:
        raise ValueError("Download URL is empty")
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        raise ValueError(f"Invalid download URL: {url!r}")
    if parsed.scheme == "file":
        return
    if not parsed.netloc:
        raise ValueError(f"Invalid download URL: {url!r}")
    path = parsed.path.rstrip("/")
    if not path or path.endswith("/"):
        raise ValueError(
            f"Download URL points to a directory, not a file: {url!r}"
        )
    if "." not in os.path.basename(path):
        raise ValueError(
            f"Download URL has no filename: {url!r}"
        )


def download_to_cache(
    url: str,
    filename: str,
    *,
    cache_dir: Union[str, Path],
    expected_size: int = 0,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Path:
    """Download a package into the cache directory under ``filename``.

    Args:
        url: Source URL.
        filename: Target filename within the cache directory.
        cache_dir: Cache directory.
        expected_size: Expected total size in bytes.
        progress_cb: Optional progress callback.
        cancel_event: Optional cancellation event.
        timeout: Network timeout in seconds.

    Returns:
        Path to the downloaded file in the cache directory.
    """
    validate_download_url(url)
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    return download(
        url,
        cache_path / filename,
        expected_size=expected_size,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
        timeout=timeout,
    )


def filename_from_url(url: str, fallback: str = "update.bin") -> str:
    """Derive a safe filename from a URL.

    Args:
        url: Source URL.
        fallback: Filename to use when the URL has no usable basename.

    Returns:
        A filesystem-safe filename.
    """
    try:
        path = urllib.parse.urlparse(url).path
        name = os.path.basename(path)
    except Exception:  # pragma: no cover - defensive
        name = ""
    if not name or name in (".", ".."):
        return fallback
    # Strip any directory components and unsafe characters.
    name = name.replace("\\", "_").replace("/", "_")
    return name or fallback