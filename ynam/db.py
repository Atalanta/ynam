"""Database initialization and schema management."""

import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".ynam" / "ynam.db"


def get_db_path() -> Path:
    """Get the default database path."""
    return DEFAULT_DB_PATH


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
                ignored INTEGER NOT NULL DEFAULT 0
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

        # Migration: Add ignored column if it doesn't exist
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        if "ignored" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN ignored INTEGER NOT NULL DEFAULT 0")

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


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


def insert_transaction(
    date: str, description: str, amount: int, db_path: Path | None = None
) -> tuple[bool, int | None]:
    """Insert a transaction into the database if it doesn't already exist.

    Args:
        date: Transaction date.
        description: Transaction description.
        amount: Transaction amount in cents.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Tuple of (inserted, duplicate_id):
        - inserted: True if transaction was inserted, False if duplicate
        - duplicate_id: ID of matching transaction if duplicate, None if inserted

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM transactions WHERE date = ? AND description = ? AND amount = ?",
            (date, description, amount),
        )
        existing = cursor.fetchone()
        if existing:
            return (False, existing[0])

        cursor.execute(
            "INSERT INTO transactions (date, description, amount) VALUES (?, ?, ?)",
            (date, description, amount),
        )
        conn.commit()
        return (True, None)
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_unreviewed_transactions(db_path: Path | None = None) -> list[dict[str, Any]]:
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
        cursor.execute("SELECT id, date, description, amount FROM transactions WHERE reviewed = 0 ORDER BY date")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_transactions(db_path: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Get all transactions.

    Args:
        db_path: Path to the database file. If None, uses default location.
        limit: Maximum number of transactions to return. If None, returns all.

    Returns:
        List of transaction dictionaries ordered by date descending.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = "SELECT id, date, description, amount, category, reviewed, ignored FROM transactions ORDER BY date DESC"
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_transaction_review(txn_id: int, category: str, db_path: Path | None = None) -> None:
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
            "UPDATE transactions SET category = ?, reviewed = 1, ignored = 0 WHERE id = ?",
            (category, txn_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_transaction_ignored(txn_id: int, db_path: Path | None = None) -> None:
    """Mark transaction as ignored (reviewed but excluded from reports).

    Args:
        txn_id: Transaction ID.
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
            "UPDATE transactions SET category = NULL, reviewed = 1, ignored = 1 WHERE id = ?",
            (txn_id,),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_category_breakdown(
    db_path: Path | None = None, since_date: str | None = None, until_date: str | None = None
) -> dict[str, int]:
    """Get spending breakdown by category.

    Args:
        db_path: Path to the database file. If None, uses default location.
        since_date: Optional start date (YYYY-MM-DD) for filtering.
        until_date: Optional end date (YYYY-MM-DD) for filtering.

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
        query = "SELECT category, SUM(amount) FROM transactions WHERE reviewed = 1 AND ignored = 0"
        params = []

        if since_date:
            query += " AND date >= ?"
            params.append(since_date)
        if until_date:
            query += " AND date < ?"
            params.append(until_date)

        query += " GROUP BY category"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows if row[0] is not None}
    finally:
        conn.close()


def get_transactions_by_category(
    category: str, db_path: Path | None = None, since_date: str | None = None, until_date: str | None = None
) -> list[dict[str, Any]]:
    """Get all transactions for a specific category.

    Args:
        category: Category name to filter by. Use "unreviewed" to show unreviewed transactions.
        db_path: Path to the database file. If None, uses default location.
        since_date: Optional start date (YYYY-MM-DD) for filtering.
        until_date: Optional end date (YYYY-MM-DD) for filtering.

    Returns:
        List of transaction dictionaries ordered by date descending.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        if category.lower() == "unreviewed":
            query = "SELECT id, date, description, amount, category, reviewed, ignored FROM transactions WHERE reviewed = 0 AND ignored = 0"
            params = []
        else:
            query = "SELECT id, date, description, amount, category, reviewed, ignored FROM transactions WHERE category = ? AND reviewed = 1 AND ignored = 0"
            params = [category]

        if since_date:
            query += " AND date >= ?"
            params.append(since_date)
        if until_date:
            query += " AND date < ?"
            params.append(until_date)

        query += " ORDER BY date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_categories(db_path: Path | None = None) -> list[str]:
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


def add_category(name: str, db_path: Path | None = None) -> None:
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


def get_most_recent_transaction_date(db_path: Path | None = None) -> str | None:
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


def get_suggested_category(description: str, db_path: Path | None = None) -> str | None:
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


def auto_categorize_by_description(description: str, category: str, db_path: Path | None = None) -> int:
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


def get_auto_allocate_rule(description: str, db_path: Path | None = None) -> str | None:
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


def set_auto_allocate_rule(description: str, category: str, db_path: Path | None = None) -> None:
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


def get_auto_ignore_rule(description: str, db_path: Path | None = None) -> bool:
    """Check if transaction description has auto-ignore rule.

    Args:
        description: Transaction description to look up.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        True if this description should be auto-ignored, False otherwise.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT description FROM auto_ignore_rules WHERE description = ?", (description,))
        return cursor.fetchone() is not None
    finally:
        conn.close()


def set_auto_ignore_rule(description: str, db_path: Path | None = None) -> None:
    """Set auto-ignore rule for a transaction description.

    Args:
        description: Transaction description to set rule for.
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
            "INSERT OR REPLACE INTO auto_ignore_rules (description) VALUES (?)",
            (description,),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_budget(category: str, month: str, db_path: Path | None = None) -> int | None:
    """Get budget amount for a category in a specific month.

    Args:
        category: Category name.
        month: Month in YYYY-MM format.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Budget amount in pence, or None if no budget set.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT amount FROM budgets WHERE month = ? AND category = ?", (month, category))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_budget(category: str, month: str, amount: int, db_path: Path | None = None) -> None:
    """Set budget amount for a category in a specific month.

    Args:
        category: Category name.
        month: Month in YYYY-MM format.
        amount: Budget amount in pence.
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
            "INSERT OR REPLACE INTO budgets (month, category, amount) VALUES (?, ?, ?)",
            (month, category, amount),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_budgets(month: str, db_path: Path | None = None) -> dict[str, int]:
    """Get all budget amounts for a specific month.

    Args:
        month: Month in YYYY-MM format.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        Dictionary mapping category names to budget amounts in pence.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT category, amount FROM budgets WHERE month = ?", (month,))
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def get_monthly_tbb(month: str, db_path: Path | None = None) -> int | None:
    """Get To Be Budgeted amount for a specific month.

    Args:
        month: Month in YYYY-MM format.
        db_path: Path to the database file. If None, uses default location.

    Returns:
        TBB amount in pence, or None if not set.

    Raises:
        sqlite3.Error: If database operation fails.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT amount FROM monthly_tbb WHERE month = ?", (month,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_monthly_tbb(month: str, amount: int, db_path: Path | None = None) -> None:
    """Set To Be Budgeted amount for a specific month.

    Args:
        month: Month in YYYY-MM format.
        amount: TBB amount in pence.
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
            "INSERT OR REPLACE INTO monthly_tbb (month, amount) VALUES (?, ?)",
            (month, amount),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
