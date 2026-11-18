"""Filesystem path resolution for the application.

The application stores user data (database, preferences, logs, cached
downloads) in a *per-user* location so that it survives application upgrades.
When the application is frozen with PyInstaller (a packaged Windows build),
the per-user location is ``%APPDATA%\\ParseCraft``. When running
from source, the project-local ``data`` directory is used so development keeps
working without polluting the user's profile.

The install directory (where the binaries live) is always derived from the
running executable and is never used for user data. This separation is what
allows the update system to replace binaries without touching user data.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Project root when running from source (``core/`` -> project root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directory name used for per-user data under %APPDATA%.
APP_DATA_DIR_NAME = "ParseCraft"


def is_frozen() -> bool:
    """Return ``True`` when running from a PyInstaller bundle.

    Returns:
        ``True`` if the application is packaged, ``False`` when run from
        source.
    """
    return bool(getattr(sys, "frozen", False))


def get_app_data_dir() -> Path:
    """Return the per-user application data directory.

    The directory is created if it does not exist. When frozen this is
    ``%APPDATA%\\ParseCraft``; otherwise it is the project-local
    ``data`` directory.

    Returns:
        Path to the per-user data directory.
    """
    if is_frozen():
        base = os.environ.get("APPDATA")
        if not base:
            # Fall back to the user's home directory if APPDATA is unavailable.
            base = str(Path.home())
        data_dir = Path(base) / APP_DATA_DIR_NAME
    else:
        data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_logs_dir() -> Path:
    """Return the per-user logs directory, creating it if needed.

    Returns:
        Path to the logs directory.
    """
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_cache_dir() -> Path:
    """Return the per-user cache directory used for update downloads.

    Returns:
        Path to the cache directory.
    """
    cache_dir = get_app_data_dir() / "downloads"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_install_dir() -> Path:
    """Return the directory that contains the application binaries.

    When frozen this is the directory containing the executable. When running
    from source it is the project root.

    Returns:
        Path to the installation directory.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_executable_path() -> Path:
    """Return the path to the running executable.

    Returns:
        Path to ``sys.executable``.
    """
    return Path(sys.executable)


def is_writable_dir(path: Path) -> bool:
    """Return ``True`` when the given directory is writable.

    Args:
        path: Directory to test.

    Returns:
        ``True`` if a temporary file can be created in the directory.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def ensure_runtime_dirs() -> Optional[Path]:
    """Create all per-user runtime directories.

    Returns:
        The application data directory, or ``None`` if creation failed.
    """
    try:
        return get_app_data_dir()
    except OSError:
        return None