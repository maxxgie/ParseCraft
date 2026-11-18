"""SQLite database initialization and schema management."""

import sqlite3
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_grammars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    grammar_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parsing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grammar_name TEXT NOT NULL,
    parser_type TEXT NOT NULL,
    input_string TEXT NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0,
    steps_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recent_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    last_opened TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite database wrapper for persistent storage.

    Handles connection management, schema initialization, and provides
    a simple interface for executing queries.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                ``data/parser_simulator.db`` relative to the project root.
        """
        if db_path is None:
            from core.paths import get_app_data_dir

            db_path = get_app_data_dir() / "parser_simulator.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        self._connect()
        self._init_schema()

    def _connect(self) -> None:
        """Establish a connection to the SQLite database."""
        try:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
            logger.info("Connected to database: %s", self.db_path)
        except sqlite3.Error as exc:
            logger.error("Failed to connect to database %s: %s", self.db_path, exc)
            raise

    def _init_schema(self) -> None:
        """Create database tables if they do not already exist."""
        if self.connection is None:
            raise RuntimeError("Database connection is not established")
        try:
            cursor = self.connection.cursor()
            cursor.executescript(SCHEMA)
            self.connection.commit()
            logger.info("Database schema initialized")
        except sqlite3.Error as exc:
            logger.error("Failed to initialize database schema: %s", exc)
            raise

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single query and return the cursor.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            The cursor after executing the query.

        Raises:
            RuntimeError: If the connection is not established.
            sqlite3.Error: If the query execution fails.
        """
        if self.connection is None:
            raise RuntimeError("Database connection is not established")
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            return cursor
        except sqlite3.Error as exc:
            logger.error("Query execution failed: %s | params: %s | error: %s", query, params, exc)
            raise

    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query string.
            params_list: List of parameter tuples.

        Returns:
            The cursor after executing the queries.

        Raises:
            RuntimeError: If the connection is not established.
            sqlite3.Error: If the query execution fails.
        """
        if self.connection is None:
            raise RuntimeError("Database connection is not established")
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, params_list)
            self.connection.commit()
            return cursor
        except sqlite3.Error as exc:
            logger.error("executemany failed: %s | error: %s", query, exc)
            raise

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a query and return a single row.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            A single row as a sqlite3.Row, or None if no rows match.
        """
        if self.connection is None:
            raise RuntimeError("Database connection is not established")
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return all matching rows.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            A list of rows as sqlite3.Row objects.
        """
        if self.connection is None:
            raise RuntimeError("Database connection is not established")
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def close(self) -> None:
        """Close the database connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")


_database_instance: Optional[Database] = None


def get_database() -> Database:
    """Return a singleton Database instance.

    Returns:
        The shared :class:`Database` instance.
    """
    global _database_instance
    if _database_instance is None:
        _database_instance = Database()
    return _database_instance
