"""Update manager facade for ParseCraft (GitHub Releases backend).

This is the developer- and application-facing entry point for the update
system. It wraps the lower-level :mod:`core.update` package and exposes a simple
:func:`check_for_updates` function that returns a :class:`UpdateCheckResult`
describing whether an update is available.

The update backend is GitHub Releases: the manifest (``manifest.json``) is read
from the ``maxxgie/ParseCraft`` repository and the installer is downloaded from
the release asset referenced by the manifest's ``download_url``.

Typical use::

    from core.updater import check_for_updates

    result = check_for_updates()
    if result.update_available:
        print(result.message)          # "Update available: 1.0.0 -> 1.1.0"
        # result.manifest.download_url -> installer URL
    else:
        print(result.message)          # "ParseCraft is up to date ..."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from core.logging_config import get_logger
from core.update.checker import CheckError, fetch_manifest
from core.update.manager import UpdateManager
from core.update.manifest import ReleaseManifest
from core.version import current_version


logger = get_logger(__name__)

# Result status values.
STATUS_UP_TO_DATE = "up_to_date"
STATUS_UPDATE_AVAILABLE = "update_available"
STATUS_ERROR = "error"


@dataclass
class UpdateCheckResult:
    """The outcome of an update check.

    Attributes:
        status: One of :data:`STATUS_UP_TO_DATE`,
            :data:`STATUS_UPDATE_AVAILABLE`, or :data:`STATUS_ERROR`.
        current_version: The installed application version.
        latest_version: The latest version published on GitHub (if known).
        update_available: ``True`` when a newer version is available.
        manifest: The parsed :class:`~core.update.manifest.ReleaseManifest`
            when an update is available.
        error: Error message when ``status`` is :data:`STATUS_ERROR`.
    """

    status: str
    current_version: str
    latest_version: str = ""
    update_available: bool = False
    manifest: Optional[ReleaseManifest] = None
    error: str = ""

    @property
    def is_update_available(self) -> bool:
        """Return ``True`` when a newer version is available."""
        return self.update_available

    @property
    def message(self) -> str:
        """Return a human-readable summary of the result."""
        if self.status == STATUS_UPDATE_AVAILABLE:
            return f"Update available: {self.current_version} -> {self.latest_version}"
        if self.status == STATUS_ERROR:
            return f"Update check failed: {self.error}"
        return f"ParseCraft is up to date (version {self.current_version})."


def _resolve_url(manager: UpdateManager, url: Optional[str]) -> Optional[str]:
    """Resolve the manifest URL using the documented priority.

    Priority is: explicit ``url`` argument, then the user's ``manifest_url``
    setting, then ``None`` (which lets the checker apply
    ``BUP_UPDATES_URL`` and :data:`~core.version.DEFAULT_MANIFEST_URL`).

    Args:
        manager: The update manager (for user settings).
        url: An explicit URL override.

    Returns:
        The resolved URL, or ``None`` to use the default resolution.
    """
    if url:
        return url
    return manager.get_settings().get("manifest_url") or None


def check_for_updates(
    manager: Optional[UpdateManager] = None, url: Optional[str] = None
) -> UpdateCheckResult:
    """Check GitHub for a newer ParseCraft release.

    This performs a single manifest fetch, compares versions, and records the
    result in the update history. It never raises for network or parse errors;
    failures are reported via :attr:`UpdateCheckResult.status == "error"`.

    Args:
        manager: Optional :class:`~core.update.manager.UpdateManager`. Defaults
            to the shared instance.
        url: Optional manifest URL override.

    Returns:
        An :class:`UpdateCheckResult`. ``status`` is ``"update_available"``,
            ``"up_to_date"``, or ``"error"``.
    """
    manager = manager or get_update_manager()
    current = manager.current_version
    resolved = _resolve_url(manager, url)

    try:
        manifest = fetch_manifest(resolved)
    except CheckError as exc:
        logger.warning("Update check failed: %s", exc)
        manager.history.record("check", detail=f"Update check failed: {exc}")
        return UpdateCheckResult(
            status=STATUS_ERROR, current_version=current, error=str(exc)
        )

    manager.preferences.set_update_preferences(
        {"last_check": datetime.now(timezone.utc).isoformat()}
    )
    latest = manifest.version

    if manifest.is_newer_than(current) and manifest.is_compatible_with(current):
        manager.history.record(
            "check", version=latest, detail="Newer version available"
        )
        return UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version=current,
            latest_version=latest,
            update_available=True,
            manifest=manifest,
        )

    manager.history.record("check", version=latest, detail="Application is up to date")
    return UpdateCheckResult(
        status=STATUS_UP_TO_DATE,
        current_version=current,
        latest_version=latest,
    )


# ---------------------------------------------------------------------------
# Shared manager
# ---------------------------------------------------------------------------
_manager: Optional[UpdateManager] = None


def get_update_manager() -> UpdateManager:
    """Return the shared :class:`UpdateManager` instance.

    Returns:
        The process-wide update manager.
    """
    global _manager
    if _manager is None:
        _manager = UpdateManager()
    return _manager


def reset_update_manager() -> None:
    """Reset the shared manager (mainly for tests)."""
    global _manager
    _manager = None


__all__ = [
    "UpdateCheckResult",
    "STATUS_UP_TO_DATE",
    "STATUS_UPDATE_AVAILABLE",
    "STATUS_ERROR",
    "check_for_updates",
    "get_update_manager",
    "reset_update_manager",
    "current_version",
]