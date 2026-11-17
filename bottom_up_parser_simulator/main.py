"""Entry point for the Bottom-Up Parser Simulator application."""

import sys

from PyQt6.QtWidgets import QApplication

from core.database import get_database
from core.logging_config import setup_logging, get_logger
from gui.main_window import MainWindow
from gui.settings import APP_NAME
from gui.theme import apply_theme

logger = get_logger(__name__)


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

    # Initialize the database
    try:
        db = get_database()
        logger.info("Database initialized")
    except Exception as exc:
        logger.exception("Failed to initialize database: %s", exc)
        return 1

    window = MainWindow()
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
