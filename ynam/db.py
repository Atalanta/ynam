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
                category TEXT,
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


def insert_transaction(date: str, description: str, amount: int, db_path: Optional[Path] = None) -> None:
    """Insert a transaction into the database.

    Args:
        date: Transaction date.
        description: Transaction description.
        amount: Transaction amount in cents.
        db_path: Path to the database file. If None, uses default location.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO transactions (date, description, amount) VALUES (?, ?, ?)",
            (date, description, amount),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_unreviewed_transactions(db_path: Optional[Path] = None) -> list[dict]:
    """Get all unreviewed transactions.

    Args:
        db_path: Path to the database file. If None, uses default location.

    Returns:
        List of transaction dictionaries.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, date, description, amount FROM transactions WHERE reviewed = 0 ORDER BY date"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_transaction_review(txn_id: int, category: str, db_path: Optional[Path] = None) -> None:
    """Update transaction category and mark as reviewed.

    Args:
        txn_id: Transaction ID.
        category: Category name.
        db_path: Path to the database file. If None, uses default location.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE transactions SET category = ?, reviewed = 1 WHERE id = ?",
            (category, txn_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_category_breakdown(db_path: Optional[Path] = None) -> dict[str, int]:
    """Get spending breakdown by category.

    Args:
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Dictionary mapping category names to total amounts in cents.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE reviewed = 1 GROUP BY category"
        )
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows if row[0] is not None}
    finally:
        conn.close()
