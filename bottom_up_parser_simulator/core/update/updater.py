"""Standalone updater process (the ``Updater.exe`` stage).

Windows locks running executables, so an update cannot overwrite them in place.
The professional solution is a *separate* updater process:

    Application.exe  ->  Updater.exe  ->  (app closes)  ->  replace files
                     ->  restart application

This module implements the updater stage. It is invoked by
:func:`core.update.installer.launch_updater` (or directly as
``python -m core.update.updater``), waits for the application process to exit,
applies the update with a full backup and automatic rollback, and then relaunches
the application.

When packaged with PyInstaller this module is built as ``Updater.exe`` (see
``packaging/updater.spec``) so it has no Python dependency at runtime.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger
from core.update.installer import apply_zip_update


logger = get_logger(__name__)


def _pid_alive(pid: int) -> bool:
    """Return ``True`` if a process with the given PID is still running.

    Args:
        pid: The process id to check.

    Returns:
        ``True`` if the process exists and has not exited.
    """
    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover - exercised on Windows
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok) and exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_for_process_exit(pid: int, timeout: float = 120.0, poll: float = 0.2) -> bool:
    """Block until the given process exits or the timeout elapses.

    Args:
        pid: Process id to wait for.
        timeout: Maximum seconds to wait.
        poll: Polling interval in seconds.

    Returns:
        ``True`` if the process exited within the timeout, ``False`` otherwise.
    """
    if pid <= 0:
        return True
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(poll)
    return not _pid_alive(pid)


def run_update(
    package: "str | Path",
    install_dir: "str | Path",
    app_exe: "Optional[str | Path]" = None,
    *,
    relaunch: bool = True,
) -> int:
    """Apply an update package and optionally relaunch the application.

    Args:
        package: Path to the update package (ZIP or installer ``*.exe``).
        install_dir: Directory containing the application binaries.
        app_exe: Application executable to relaunch after a successful update.
        relaunch: Whether to relaunch the application after applying.

    Returns:
        ``0`` on success, ``1`` on failure.
    """
    package = Path(package)
    if package.suffix.lower() == ".exe":
        # Installer package: run it silently and relaunch afterwards.
        try:
            subprocess.Popen(
                [str(package), "/SILENT", "/SP-", "/NORESTART"],
                close_fds=True,
            )
            logger.info("Launched installer: %s", package)
        except OSError as exc:  # pragma: no cover - platform dependent
            logger.error("Failed to launch installer: %s", exc)
            return 1
        if relaunch and app_exe:
            try:
                subprocess.Popen([str(app_exe)], close_fds=True)
                logger.info("Relaunched application: %s", app_exe)
            except OSError as exc:  # pragma: no cover - platform dependent
                logger.error("Failed to relaunch application: %s", exc)
        return 0

    result = apply_zip_update(package, install_dir)
    if not result.success:
        logger.error("Updater failed to apply update: %s", result.error)
        return 1
    logger.info(
        "Updater applied update successfully (backup at %s)", result.backup_dir
    )
    if relaunch and app_exe:
        try:
            subprocess.Popen([str(app_exe)], close_fds=True)
            logger.info("Relaunched application: %s", app_exe)
        except OSError as exc:  # pragma: no cover - platform dependent
            logger.error("Failed to relaunch application: %s", exc)
    return 0


def main(argv: Optional[list] = None) -> int:
    """Entry point for the standalone updater.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` success, ``1`` failure).
    """
    parser = argparse.ArgumentParser(description="ParseCraft updater")
    parser.add_argument("--package", required=True, help="Path to the update package")
    parser.add_argument("--install-dir", required=True, help="Application install directory")
    parser.add_argument("--app-exe", default=None, help="Application executable to relaunch")
    parser.add_argument("--pid", type=int, default=0, help="PID of the app to wait for")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Seconds to wait for the app to exit"
    )
    parser.add_argument(
        "--no-relaunch", action="store_true", help="Do not relaunch the application"
    )
    args = parser.parse_args(argv)

    if args.pid:
        logger.info("Waiting for application (pid %s) to exit", args.pid)
        exited = wait_for_process_exit(args.pid, args.timeout)
        if not exited:
            logger.error("Application did not exit within %.1fs", args.timeout)
            return 1

    return run_update(
        args.package,
        args.install_dir,
        args.app_exe,
        relaunch=not args.no_relaunch,
    )


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())