"""Application settings and constants."""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path
DATABASE_PATH = DATA_DIR / "parser_simulator.db"

# Application metadata
APP_NAME = "Bottom-Up Parser Simulator"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "Compiler Construction"

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
