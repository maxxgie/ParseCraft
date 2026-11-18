"""Background worker threads for update checks and downloads.

The update system must never block the UI. These :class:`QThread` subclasses run
network I/O off the GUI thread and report results back via signals, following
the same pattern used elsewhere in the application (e.g. parsing workers).
"""

from __future__ import annotations

import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.logging_config import get_logger
from core.update.checker import CheckError
from core.update.downloader import DownloadCancelled, DownloadError
from core.update.manager import UpdateManager
from core.update.verifier import VerificationError


logger = get_logger(__name__)


class CheckWorker(QThread):
    """Fetch the latest release manifest in the background.

    Signals:
        check_finished(object, str): Emitted with the
            :class:`~core.update.manifest.ReleaseManifest` (or ``None`` when up
            to date) and an error string (empty on success).
    """

    check_finished = pyqtSignal(object, str)

    def __init__(self, manager: UpdateManager, url: Optional[str] = None) -> None:
        """Initialize the worker.

        Args:
            manager: The :class:`UpdateManager` to use.
            url: Optional manifest URL override.
        """
        super().__init__()
        self._manager = manager
        self._url = url

    def run(self) -> None:  # noqa: D401 (Qt override)
        """Perform the update check and emit the result."""
        try:
            manifest = self._manager.check(url=self._url)
            self.check_finished.emit(manifest, "")
        except CheckError as exc:
            logger.warning("Update check failed: %s", exc)
            self.check_finished.emit(None, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error during update check")
            self.check_finished.emit(None, f"Unexpected error: {exc}")


class DownloadWorker(QThread):
    """Download and verify an update package in the background.

    Signals:
        download_progress(int, int): Emitted with ``(downloaded, total)`` bytes.
        download_finished(object, str): Emitted with the downloaded package path
            (or ``None``) and an error string.
        download_cancelled(): Emitted when the download was cancelled.
    """

    download_progress = pyqtSignal(int, int)
    download_finished = pyqtSignal(object, str)
    download_cancelled = pyqtSignal()

    def __init__(self, manager: UpdateManager, manifest) -> None:
        """Initialize the worker.

        Args:
            manager: The :class:`UpdateManager` to use.
            manifest: The manifest describing the package to download.
        """
        super().__init__()
        self._manager = manager
        self._manifest = manifest
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation of the in-flight download."""
        self._cancel_event.set()

    def run(self) -> None:  # noqa: D401 (Qt override)
        """Download the package and emit progress/result signals."""
        try:
            path = self._manager.download(
                self._manifest,
                progress_cb=lambda d, t: self.download_progress.emit(d, t),
                cancel_event=self._cancel_event,
            )
            self.download_finished.emit(str(path), "")
        except DownloadCancelled:
            self.download_cancelled.emit()
        except (DownloadError, VerificationError) as exc:
            logger.warning("Update download failed: %s", exc)
            self.download_finished.emit(None, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error during update download")
            self.download_finished.emit(None, f"Unexpected error: {exc}")