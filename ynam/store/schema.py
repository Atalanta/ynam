"""Database schema initialization and migrations."""

import os
import sqlite3
from pathlib import Path


def get_xdg_data_home() -> Path:
    """Get XDG data directory, with fallback to ~/.local/share."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data)
    return Path.home() / ".local" / "share"


def get_db_path() -> Path:
    """Get the default database path (XDG compliant)."""
    return get_xdg_data_home() / "ynam" / "ynam.db"


def get_sources_dir() -> Path:
    """Get the sources directory for CSV imports (XDG compliant)."""
    return get_xdg_data_home() / "ynam" / "sources"


def database_exists(db_path: Path | None = None) -> bool:
    """Check if the database file exists.

    Args:
        db_path: Path to check. If None, uses default location.

    Returns:
        True if database exists, False otherwise.
    """
    if db_path is None:
        db_path = get_db_path()
    return db_path.exists()


def init_database(db_path: Path | None = None) -> None:
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                category TEXT,
                reviewed INTEGER NOT NULL DEFAULT 0,
                ignored INTEGER NOT NULL DEFAULT 0,
                source TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_allocate_rules (
                description TEXT PRIMARY KEY,
                category TEXT NOT NULL
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_ignore_rules (
                description TEXT PRIMARY KEY
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                month TEXT NOT NULL,
                category TEXT NOT NULL,
                amount INTEGER NOT NULL,
                PRIMARY KEY (month, category)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_tbb (
                month TEXT PRIMARY KEY,
                amount INTEGER NOT NULL
            )
        """
        )

        # Migrations for older databases (must run before creating indexes on new columns)
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]

        # Migration: Add 'ignored' column if missing
        if "ignored" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN ignored INTEGER NOT NULL DEFAULT 0")

        # Migration: Add 'source' column if missing
        if "source" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN source TEXT")

        # Migration: Add 'external_id' column if missing
        if "external_id" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN external_id TEXT")

        # Migration: Add 'created_at' column if missing
        if "created_at" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'))")

        # Create indexes for common queries (after migrations ensure columns exist)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_category_date ON transactions(category, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_desc_reviewed ON transactions(description, reviewed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_source ON transactions(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_source_external_id ON transactions(source, external_id)")

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
