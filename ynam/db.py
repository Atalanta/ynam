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
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_allocate_rules (
                description TEXT PRIMARY KEY,
                category TEXT NOT NULL
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


def get_all_categories(db_path: Optional[Path] = None) -> list[str]:
    """Get all category names.

    Args:
        db_path: Path to the database file. If None, uses default location.

    Returns:
        List of category names sorted alphabetically.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM categories ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def add_category(name: str, db_path: Optional[Path] = None) -> None:
    """Add a new category.

    Args:
        name: Category name.
        db_path: Path to the database file. If None, uses default location.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_most_recent_transaction_date(db_path: Optional[Path] = None) -> Optional[str]:
    """Get the date of the most recent transaction.

    Args:
        db_path: Path to the database file. If None, uses default location.

    Returns:
        The date of the most recent transaction in ISO format, or None if no transactions exist.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT date FROM transactions ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_suggested_category(description: str, db_path: Optional[Path] = None) -> Optional[str]:
    """Get suggested category based on previous transactions with same description.

    Args:
        description: Transaction description to match.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Most commonly used category for this description, or None if no match found.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT category, COUNT(*) as count
            FROM transactions
            WHERE description = ? AND reviewed = 1 AND category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
            LIMIT 1
            """,
            (description,),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def auto_categorize_by_description(description: str, category: str, db_path: Optional[Path] = None) -> int:
    """Auto-categorize all unreviewed transactions with matching description.

    Args:
        description: Transaction description to match.
        category: Category to assign.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Number of transactions updated.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE transactions SET category = ?, reviewed = 1 WHERE description = ? AND reviewed = 0",
            (category, description),
        )
        count = cursor.rowcount
        conn.commit()
        return count
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_auto_allocate_rule(description: str, db_path: Optional[Path] = None) -> Optional[str]:
    """Get auto-allocation rule for a transaction description.

    Args:
        description: Transaction description to look up.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Category to auto-allocate, or None if no rule exists.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT category FROM auto_allocate_rules WHERE description = ?", (description,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_auto_allocate_rule(description: str, category: str, db_path: Optional[Path] = None) -> None:
    """Set auto-allocation rule for a transaction description.

    Args:
        description: Transaction description to set rule for.
        category: Category to auto-allocate.
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
            "INSERT OR REPLACE INTO auto_allocate_rules (description, category) VALUES (?, ?)",
            (description, category),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
