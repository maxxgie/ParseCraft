"""Applying update packages with backup and rollback.

Two application strategies are supported:

* **ZIP overlay** (:func:`apply_zip_update`) — the downloaded package is a ZIP
  whose root contains the new application files. The current install directory
  is backed up, the new files are overlaid, and any failure triggers a full
  rollback from the backup. This is the strategy used for portable/zip
  distributions and is fully testable without external tooling.

* **Installer launch** (:func:`launch_installer`) — the downloaded package is a
  Windows installer (``*.exe``). The running application exits and the
  installer applies the update in place. This delegates file replacement and
  rollback to the installer, which is the most robust option on Windows where
  running binaries are locked.

Deferred updates ("Install on Next Restart") are persisted as a *pending
update* marker (:func:`write_pending_update`) and applied at the next launch
before the user interface is shown (:func:`apply_pending_update`).

User data lives in a per-user directory (see :mod:`core.paths`) and is never
touched by either strategy, so updates cannot destroy projects, preferences,
logs, or history.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging_config import get_logger
from core.paths import get_app_data_dir, get_install_dir


logger = get_logger(__name__)

PENDING_UPDATE_FILENAME = "pending_update.json"


class InstallError(Exception):
    """Raised when an update cannot be applied."""


@dataclass
class ApplyResult:
    """Outcome of an update application attempt.

    Attributes:
        success: Whether the update was applied successfully.
        backup_dir: Path to the backup created, if any.
        error: Error message when ``success`` is ``False``.
        requires_restart: Whether the application must restart.
    """

    success: bool
    backup_dir: Optional[Path] = None
    error: Optional[str] = None
    requires_restart: bool = True


@dataclass
class PendingUpdate:
    """A deferred update to apply at the next launch.

    Attributes:
        manifest: The manifest dict describing the update.
        package_path: Path to the downloaded package.
        created_at: ISO-8601 creation timestamp.
    """

    manifest: Dict[str, Any]
    package_path: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict."""
        return {
            "manifest": self.manifest,
            "package_path": self.package_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingUpdate":
        """Build a :class:`PendingUpdate` from a dict."""
        return cls(
            manifest=dict(data.get("manifest", {})),
            package_path=str(data.get("package_path", "")),
            created_at=str(data.get("created_at", "")),
        )


# ---------------------------------------------------------------------------
# ZIP overlay
# ---------------------------------------------------------------------------
def _safe_extract(zip_path: Path, dest_dir: Path) -> None:
    """Extract a ZIP into ``dest_dir`` with zip-slip protection.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory to extract into.

    Raises:
        InstallError: If the archive is invalid or contains unsafe paths.
    """
    dest_root = dest_dir.resolve()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                target = (dest_dir / member).resolve()
                if not str(target).startswith(str(dest_root)):
                    raise InstallError(f"Unsafe path in update package: {member}")
            archive.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise InstallError(f"Update package is not a valid ZIP: {exc}") from exc
    except OSError as exc:
        raise InstallError(f"Failed to extract update package: {exc}") from exc


def _copy_overlay(src_dir: Path, dst_dir: Path) -> None:
    """Copy the contents of ``src_dir`` over ``dst_dir``, overwriting files.

    Args:
        src_dir: Source directory (extracted payload).
        dst_dir: Destination (install directory).
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    for entry in src_dir.iterdir():
        target = dst_dir / entry.name
        if entry.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(entry, target)
        else:
            if target.exists() or target.is_symlink():
                target.unlink()
            shutil.copy2(entry, target)


def apply_zip_update(
    package_zip: "str | Path",
    install_dir: "str | Path | None" = None,
    *,
    backup: bool = True,
) -> ApplyResult:
    """Apply a ZIP update package to the install directory.

    The current install directory is backed up first. On any failure the backup
    is restored and the result reports ``success=False``.

    Args:
        package_zip: Path to the downloaded ZIP package.
        install_dir: Target install directory. Defaults to
            :func:`core.paths.get_install_dir`.
        backup: Whether to create a backup before applying.

    Returns:
        An :class:`ApplyResult` describing the outcome.
    """
    package = Path(package_zip)
    if not package.exists():
        return ApplyResult(success=False, error=f"Update package not found: {package}")

    target = Path(install_dir) if install_dir is not None else get_install_dir()

    staging: Optional[Path] = None
    backup_dir: Optional[Path] = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="bup_update_"))
        _safe_extract(package, staging)

        # A ZIP may contain a single top-level folder; if so, descend into it.
        payload = _resolve_payload_root(staging)

        if backup and target.exists():
            backup_dir = _make_backup(target)

        _copy_overlay(payload, target)
        logger.info("Applied ZIP update from %s to %s", package, target)
        return ApplyResult(success=True, backup_dir=backup_dir, requires_restart=True)
    except InstallError as exc:
        logger.error("ZIP update failed: %s", exc)
        _rollback(target, backup_dir)
        return ApplyResult(success=False, backup_dir=backup_dir, error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error applying ZIP update")
        _rollback(target, backup_dir)
        return ApplyResult(
            success=False, backup_dir=backup_dir, error=f"Unexpected error: {exc}"
        )
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def _resolve_payload_root(staging: Path) -> Path:
    """Return the directory that actually contains the payload files.

    If the ZIP extracts to a single top-level directory (a common convention),
    that directory is returned; otherwise ``staging`` itself is returned.

    Args:
        staging: The extraction directory.

    Returns:
        The directory whose contents should overlay the install directory.
    """
    entries = list(staging.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return staging


def _make_backup(target: Path) -> Path:
    """Create a backup copy of ``target``.

    Args:
        target: Directory to back up.

    Returns:
        Path to the backup directory.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_dir = target.parent / f"{target.name}.bak-{timestamp}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
    shutil.copytree(target, backup_dir)
    return backup_dir


def _rollback(target: Path, backup_dir: Optional[Path]) -> None:
    """Restore ``target`` from ``backup_dir`` after a failed update.

    Args:
        target: The (possibly corrupted) install directory.
        backup_dir: The backup to restore from, if any.
    """
    if backup_dir is None or not backup_dir.exists():
        return
    try:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(backup_dir, target)
        logger.info("Rolled back install directory from %s", backup_dir)
    except Exception:  # pragma: no cover - best effort
        logger.exception("Rollback failed; backup preserved at %s", backup_dir)


# ---------------------------------------------------------------------------
# Installer launch
# ---------------------------------------------------------------------------
def launch_installer(installer_path: "str | Path", *, silent: bool = True) -> subprocess.Popen:
    """Launch a Windows installer to apply an update.

    The caller is responsible for exiting the application afterwards so the
    installer can replace locked binaries.

    Args:
        installer_path: Path to the installer executable.
        silent: Whether to run the installer silently.

    Returns:
        The launched :class:`subprocess.Popen` handle.

    Raises:
        InstallError: If the installer path does not exist.
    """
    path = Path(installer_path)
    if not path.exists():
        raise InstallError(f"Installer not found: {path}")
    args: List[str] = [str(path)]
    if silent:
        # Inno Setup silent flags.
        args += ["/SILENT", "/SP-", "/NORESTART"]
    logger.info("Launching installer: %s", args)
    return subprocess.Popen(args, close_fds=True)


def launch_updater(
    package_path: "str | Path",
    install_dir: "str | Path",
    app_exe: "str | Path",
    *,
    pid: Optional[int] = None,
    updater_exe: "Optional[str | Path]" = None,
    timeout: float = 120.0,
) -> subprocess.Popen:
    """Launch the standalone updater process to apply an update.

    The updater waits for ``pid`` (the running application) to exit, applies the
    update with a backup, and relaunches ``app_exe``. When packaged, a dedicated
    ``Updater.exe`` next to the application executable is preferred; otherwise
    the updater runs via ``python -m core.update.updater`` (development).

    Args:
        package_path: Path to the downloaded update package.
        install_dir: Application install directory.
        app_exe: Application executable to relaunch after updating.
        pid: PID of the application process to wait for. Defaults to the
            current process.
        updater_exe: Optional explicit path to an ``Updater.exe``.
        timeout: Seconds the updater waits for the application to exit.

    Returns:
        The launched :class:`subprocess.Popen` handle.

    Raises:
        InstallError: If the package does not exist or the updater cannot start.
    """
    package = Path(package_path)
    if not package.exists():
        raise InstallError(f"Update package not found: {package}")

    pid = pid if pid is not None else os.getpid()

    args: List[str] = [
        "--package",
        str(package),
        "--install-dir",
        str(install_dir),
        "--app-exe",
        str(app_exe),
        "--pid",
        str(pid),
        "--timeout",
        str(timeout),
    ]

    if updater_exe is None and getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for name in ("Updater.exe", "updater.exe"):
            candidate = exe_dir / name
            if candidate.exists():
                updater_exe = candidate
                break

    if updater_exe is not None:
        cmd: List[str] = [str(updater_exe)] + args
    else:
        cmd = [sys.executable, "-m", "core.update.updater"] + args

    creationflags = 0
    if os.name == "nt":  # pragma: no cover - Windows only
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    logger.info("Launching updater: %s", cmd)
    try:
        return subprocess.Popen(cmd, close_fds=True, creationflags=creationflags)
    except OSError as exc:
        raise InstallError(f"Failed to launch updater: {exc}") from exc


def relaunch_application() -> None:
    """Relaunch the current application.

    Uses the frozen executable when packaged, otherwise ``python main.py``.
    This is intended to be called just before the process exits.
    """
    if getattr(sys, "frozen", False):
        args = [sys.executable] + sys.argv[1:]
    else:
        main_py = Path(__file__).resolve().parent.parent / "main.py"
        args = [sys.executable, str(main_py)] + sys.argv[1:]
    logger.info("Relaunching application: %s", args)
    subprocess.Popen(args, close_fds=True)


# ---------------------------------------------------------------------------
# Pending (deferred) updates
# ---------------------------------------------------------------------------
def _pending_path() -> Path:
    """Return the path to the pending-update marker file."""
    return get_app_data_dir() / PENDING_UPDATE_FILENAME


def write_pending_update(manifest: Dict[str, Any], package_path: "str | Path") -> Path:
    """Persist a deferred update to apply at the next launch.

    Args:
        manifest: The manifest dict (as returned by ``ReleaseManifest.to_dict``).
        package_path: Path to the downloaded package.

    Returns:
        Path to the written marker file.
    """
    marker = PendingUpdate(
        manifest=dict(manifest),
        package_path=str(package_path),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    path = _pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marker.to_dict(), indent=2), encoding="utf-8")
    logger.info("Wrote pending update marker: %s", path)
    return path


def read_pending_update() -> Optional[PendingUpdate]:
    """Read the pending-update marker, if any.

    Returns:
        A :class:`PendingUpdate` or ``None`` if no pending update exists.
    """
    path = _pending_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PendingUpdate.from_dict(data)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read pending update marker: %s", exc)
        return None


def clear_pending_update() -> None:
    """Remove the pending-update marker if it exists."""
    path = _pending_path()
    try:
        if path.exists():
            path.unlink()
            logger.info("Cleared pending update marker")
    except OSError:
        logger.exception("Failed to clear pending update marker")


def apply_pending_update() -> Optional[ApplyResult]:
    """Apply a deferred update if one is pending.

    This should be called at application startup, before the main window is
    shown. The marker is cleared whether the update succeeds or fails so the
    application is never stuck in a pending state.

    Returns:
        An :class:`ApplyResult` if a pending update was applied, else ``None``.
    """
    pending = read_pending_update()
    if pending is None:
        return None
    try:
        package_type = str(pending.manifest.get("package_type", "zip")).lower()
        if package_type == "installer":
            launch_installer(pending.package_path, silent=True)
            result = ApplyResult(success=True, requires_restart=True)
        else:
            result = apply_zip_update(pending.package_path, get_install_dir())
        return result
    finally:
        clear_pending_update()