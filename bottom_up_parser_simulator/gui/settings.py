"""Application settings and constants.

This module is the public settings facade for the GUI layer. Canonical
application metadata lives in :mod:`core.version` and per-user path resolution
lives in :mod:`core.paths`; the values are re-exported here so existing imports
(``from gui.settings import APP_VERSION``) keep working unchanged.

User data is stored in a per-user location (see :func:`core.paths.get_app_data_dir`)
so that application upgrades never destroy saved grammars, preferences, logs,
or recent files.
"""

from pathlib import Path

from core.paths import get_app_data_dir, get_install_dir, is_frozen
from core.version import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
    BUILD_NUMBER,
    RELEASE_DATE,
    UPDATE_CHANNEL,
)

# Project root directory (source checkout).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directory (per-user when frozen, project-local in development).
DATA_DIR = get_app_data_dir()

# Database path (kept inside the per-user data directory).
DATABASE_PATH = DATA_DIR / "parser_simulator.db"

# Installation directory (binaries). Never used for user data.
INSTALL_DIR = get_install_dir()

# UI defaults
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800

# Parser types
PARSER_TYPE_LR0 = "LR(0)"
PARSER_TYPE_SLR1 = "SLR(1)"
PARSER_TYPE_CLR1 = "CLR(1)"
PARSER_TYPE_LALR1 = "LALR(1)"

ALL_PARSER_TYPES = [
    PARSER_TYPE_LR0,
    PARSER_TYPE_SLR1,
    PARSER_TYPE_CLR1,
    PARSER_TYPE_LALR1,
]

# Grammar constants
EPSILON = "ε"
END_MARKER = "$"
AUGMENTED_START_MARKER = "S'"

__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "DATABASE_PATH",
    "INSTALL_DIR",
    "APP_NAME",
    "APP_VERSION",
    "APP_ORGANIZATION",
    "BUILD_NUMBER",
    "RELEASE_DATE",
    "UPDATE_CHANNEL",
    "DEFAULT_WINDOW_WIDTH",
    "DEFAULT_WINDOW_HEIGHT",
    "PARSER_TYPE_LR0",
    "PARSER_TYPE_SLR1",
    "PARSER_TYPE_CLR1",
    "PARSER_TYPE_LALR1",
    "ALL_PARSER_TYPES",
    "EPSILON",
    "END_MARKER",
    "AUGMENTED_START_MARKER",
    "is_frozen",
]