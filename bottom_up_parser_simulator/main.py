"""Entry point for the ParseCraft application."""

import sys

from PyQt6.QtWidgets import QApplication

from core.database import get_database
from core.logging_config import setup_logging, get_logger
from core.paths import get_install_dir, is_frozen
from core.update.installer import (
    apply_pending_update,
    clear_pending_update,
    launch_installer,
    launch_updater,
    read_pending_update,
    relaunch_application,
)
from app.dashboard import show_dashboard
from gui.settings import APP_NAME
from gui.theme import apply_theme

logger = get_logger(__name__)


def _apply_pending_update() -> bool:
    """Apply a deferred update before the UI starts.

    When packaged (frozen) the update is applied by a *separate* updater
    process so that locked, running executables are never overwritten in place;
    the application then exits so the updater can replace files and relaunch.
    When running from source the update is applied in-process (safe because the
    install directory is not locked).

    Returns:
        ``True`` if the application should exit (an update was applied or an
        installer/updater was launched), ``False`` to continue launching.
    """
    try:
        pending = read_pending_update()
        if pending is None:
            return False
        is_installer = (
            str(pending.manifest.get("package_type", "zip")).lower() == "installer"
        )
        if is_frozen():
            # Packaged: hand off to an external process, then exit.
            if is_installer:
                launch_installer(pending.package_path, silent=True)
            else:
                launch_updater(
                    pending.package_path,
                    install_dir=get_install_dir(),
                    app_exe=sys.executable,
                )
            clear_pending_update()
            logger.info("Launched external updater for pending update")
            return True

        # Source / tests: apply in-process.
        result = apply_pending_update()
        if result is not None and result.success:
            logger.info("Pending update applied (version %s)", pending.manifest.get("version"))
            if not is_installer:
                relaunch_application()
            return True
        if result is not None and not result.success:
            logger.error("Pending update failed, continuing with current version: %s", result.error)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to apply pending update")
    return False


def main() -> int:
    """Launch the application.

    Returns:
        The application exit code.
    """
    setup_logging()
    logger.info("Starting %s", APP_NAME)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app)

    # Apply any update that was deferred to "next restart" before UI startup.
    if _apply_pending_update():
        return 0

    # Initialize the database
    try:
        db = get_database()
        logger.info("Database initialized")
    except Exception as exc:
        logger.exception("Failed to initialize database: %s", exc)
        return 1

    window = show_dashboard()
    window.show()

    try:
        return app.exec()
    except SystemExit as exc:
        logger.info("Application exiting with code %s", exc.code)
        return int(exc.code) if isinstance(exc.code, int) else 0
    finally:
        db.close()
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    sys.exit(main())
