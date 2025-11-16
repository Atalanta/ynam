"""Database initialization and schema management."""

import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path.home() / ".ynam" / "ynam.db"


def get_db_path() -> Path:
    """Get the default database path."""
    return DEFAULT_DB_PATH


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize the database with the required schema.

    Args:
        db_path: Path to the database file. If None, uses default location.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reviewed INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def database_exists(db_path: Optional[Path] = None) -> bool:
    """Check if the database file exists.

    Args:
        db_path: Path to check. If None, uses default location.

    Returns:
        True if database exists, False otherwise.
    """
    if db_path is None:
        db_path = get_db_path()
    return db_path.exists()
