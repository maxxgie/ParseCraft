"""Entry point for the standalone Updater executable.

This tiny script exists so PyInstaller can freeze the updater stage
(:mod:`core.update.updater`) into a dedicated ``Updater.exe`` with no console
dependency on the main application.
"""

import sys

from core.update.updater import main


if __name__ == "__main__":
    sys.exit(main())