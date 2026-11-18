"""High-level update orchestration.

:class:`UpdateManager` is the single entry point the GUI uses to check for,
download, verify, and install updates. It combines:

* :mod:`core.update.checker` — fetch and compare manifests,
* :mod:`core.update.downloader` — download packages with progress/cancel,
* :mod:`core.update.verifier` — SHA-256 integrity (and optional signature),
* :mod:`core.update.installer` — apply updates with backup/rollback,
* :mod:`core.update.history` — persist an ``update_history.json`` log,
* :mod:`core.preferences` — persist update settings.

Every consequential action is recorded in the update history so the user can
review what happened from the settings dialog.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List, Optional

from core.logging_config import get_logger
from core.paths import get_cache_dir, get_install_dir, is_frozen
from core.preferences import Preferences, get_preferences
from core.update.checker import CheckError, check_for_update
from core.update.downloader import (
    DownloadCancelled,
    DownloadError,
    download_to_cache,
    filename_from_url,
    validate_download_url,
)
from core.update.history import UpdateHistoryStore
from core.update.installer import (
    ApplyResult,
    InstallError,
    apply_pending_update,
    apply_zip_update,
    launch_installer,
    launch_updater,
    write_pending_update,
)
from core.update.manifest import ReleaseManifest
from core.update.verifier import VerificationError, verify_package
from core.version import current_version


logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], None]


def _notes_list(manifest: ReleaseManifest) -> List[str]:
    """Split a manifest's release notes into a list of change lines.

    Args:
        manifest: The manifest.

    Returns:
        A list of non-empty change strings.
    """
    text = (manifest.release_notes or "").strip()
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


class UpdateManager:
    """Coordinates the full update lifecycle.

    Attributes:
        preferences: The preferences store used for settings.
        history: The update history store (``update_history.json``).
    """

    def __init__(
        self,
        preferences: Optional[Preferences] = None,
        history: Optional[UpdateHistoryStore] = None,
    ) -> None:
        """Initialize the manager.

        Args:
            preferences: Optional preferences store. Defaults to the shared
                :func:`core.preferences.get_preferences` instance.
            history: Optional update history store. Defaults to a store backed
                by ``<app_data_dir>/update_history.json``.
        """
        self.preferences = preferences or get_preferences()
        self.history = history or UpdateHistoryStore()

    # -- version ---------------------------------------------------------
    @property
    def current_version(self) -> str:
        """Return the installed application version string."""
        return str(current_version())

    # -- settings --------------------------------------------------------
    def get_settings(self) -> dict:
        """Return the update preferences."""
        return self.preferences.get_update_preferences()

    def update_settings(self, values: dict) -> None:
        """Persist update preferences.

        Args:
            values: Mapping of preference keys to values.
        """
        self.preferences.set_update_preferences(values)

    def should_check(self) -> bool:
        """Return ``True`` if an automatic update check should run at startup."""
        settings = self.get_settings()
        return bool(settings.get("auto_check") and settings.get("check_on_startup"))

    # -- history ---------------------------------------------------------
    def get_history(self) -> list:
        """Return the update history (newest first)."""
        return self.history.entries()

    def _record(
        self,
        event: str,
        version: str = "",
        detail: str = "",
        changes: Optional[List[str]] = None,
    ) -> None:
        """Append an entry to the update history.

        Args:
            event: Event type.
            version: Associated version.
            detail: Human-readable detail.
            changes: Optional release-note lines.
        """
        self.history.record(event, version=version, detail=detail, changes=changes)

    # -- check -----------------------------------------------------------
    def check(
        self, *, url: Optional[str] = None, force: bool = True
    ) -> Optional[ReleaseManifest]:
        """Check for a newer version.

        Args:
            url: Optional manifest URL override. When omitted, the URL is
                resolved from preferences, then environment, then default.
            force: When ``False`` and a check was performed recently, the
                result is still fetched (kept for API clarity).

        Returns:
            A :class:`ReleaseManifest` if a newer version exists, else ``None``.

        Raises:
            CheckError: If the update server cannot be reached or the manifest
                is invalid.
        """
        settings = self.get_settings()
        resolved = url or settings.get("manifest_url") or None
        manifest = check_for_update(self.current_version, url=resolved)
        if manifest is not None:
            self._record(
                "check",
                version=manifest.version,
                detail="Newer version available",
                changes=_notes_list(manifest),
            )
        else:
            self._record("check", detail="Application is up to date")
        self.preferences.set_update_preferences({"last_check": _now_iso()})
        return manifest

    # -- download --------------------------------------------------------
    def download(
        self,
        manifest: ReleaseManifest,
        *,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Path:
        """Download and verify the update package.

        Args:
            manifest: The manifest describing the package.
            progress_cb: Optional progress callback.
            cancel_event: Optional cancellation event.

        Returns:
            Path to the verified package in the cache directory.

        Raises:
            DownloadError: If the download fails.
            DownloadCancelled: If the download is cancelled.
            VerificationError: If integrity verification fails.
        """
        filename = filename_from_url(
            manifest.download_url,
            fallback=f"update-{manifest.version}.zip",
        )
        validate_download_url(manifest.download_url)
        package_path = download_to_cache(
            manifest.download_url,
            filename,
            cache_dir=get_cache_dir(),
            expected_size=manifest.size,
            progress_cb=progress_cb,
            cancel_event=cancel_event,
        )
        # Integrity verification (mandatory).
        if manifest.sha256:
            verify_package(package_path, manifest.sha256)
        self._record(
            "download",
            version=manifest.version,
            detail=f"Downloaded {package_path.name}",
        )
        return package_path

    # -- install ---------------------------------------------------------
    def install_now(
        self, package_path: "str | Path", manifest: ReleaseManifest
    ) -> ApplyResult:
        """Install an update immediately.

        For ZIP packages when running as a packaged Windows build, a separate
        :class:`~core.update.installer`-style *updater* process is spawned so
        that running (locked) executables are not overwritten in place; the
        updater waits for this process to exit, applies the update with a
        backup, and relaunches the application. When running from source (or in
        tests) the ZIP is applied in-process, which is safe because the install
        directory is not locked.

        For installer packages the Windows installer is launched; the caller
        must then exit the application.

        Args:
            package_path: Path to the downloaded package.
            manifest: The manifest describing the package.

        Returns:
            An :class:`ApplyResult` describing the outcome.
        """
        package_type = (manifest.package_type or "zip").lower()
        if package_type == "installer":
            try:
                launch_installer(package_path, silent=True)
                result = ApplyResult(success=True, requires_restart=True)
            except Exception as exc:  # pragma: no cover - platform dependent
                logger.exception("Failed to launch installer")
                result = ApplyResult(success=False, error=str(exc))
        elif is_frozen():
            # Packaged: hand off to the external updater process.
            try:
                launch_updater(
                    package_path,
                    install_dir=get_install_dir(),
                    app_exe=_current_executable(),
                )
                result = ApplyResult(success=True, requires_restart=True)
            except InstallError as exc:
                logger.exception("Failed to launch updater")
                result = ApplyResult(success=False, error=str(exc))
        else:
            result = apply_zip_update(package_path)

        if result.success:
            self._record(
                "install",
                version=manifest.version,
                detail="Update installed"
                + (" (restart required)" if result.requires_restart else ""),
                changes=_notes_list(manifest),
            )
        else:
            self._record(
                "rollback",
                version=manifest.version,
                detail=result.error or "Install failed; rolled back",
            )
        return result

    def schedule_for_restart(
        self, package_path: "str | Path", manifest: ReleaseManifest
    ) -> Path:
        """Defer an update to be applied at the next launch.

        Args:
            package_path: Path to the downloaded package.
            manifest: The manifest describing the package.

        Returns:
            Path to the written pending-update marker.
        """
        marker = write_pending_update(manifest.to_dict(), package_path)
        self._record(
            "install",
            version=manifest.version,
            detail="Update scheduled for next restart",
            changes=_notes_list(manifest),
        )
        return marker

    def apply_pending(self) -> Optional[ApplyResult]:
        """Apply a deferred update if one is pending.

        Returns:
            An :class:`ApplyResult` if applied, else ``None``.
        """
        return apply_pending_update()

    # -- convenience -----------------------------------------------------
    def check_and_download(
        self,
        *,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> "tuple[Optional[ReleaseManifest], Optional[Path]]":
        """Check for an update and download it if available.

        Args:
            progress_cb: Optional progress callback.
            cancel_event: Optional cancellation event.

        Returns:
            A ``(manifest, package_path)`` tuple. Both are ``None`` when no
            update is available; ``package_path`` is ``None`` if the download
            was cancelled.

        Raises:
            CheckError: If the update server cannot be reached.
            DownloadError: If the download fails.
            VerificationError: If integrity verification fails.
        """
        manifest = self.check()
        if manifest is None:
            return None, None
        try:
            package_path = self.download(
                manifest, progress_cb=progress_cb, cancel_event=cancel_event
            )
        except DownloadCancelled:
            self._record("error", version=manifest.version, detail="Download cancelled")
            return manifest, None
        return manifest, package_path


def _current_executable() -> str:
    """Return the path to the running executable (or interpreter)."""
    import sys

    return sys.executable


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()