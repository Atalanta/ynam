#!/usr/bin/env python3
"""Generate database schema reference documentation from actual schema."""

import re
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import ynam
sys.path.insert(0, str(Path(__file__).parent.parent))

from ynam.store.schema import init_database


def parse_create_table(sql: str) -> tuple[str, list[dict[str, str]]]:
    """Parse CREATE TABLE SQL to extract table name and columns.

    Returns:
        Tuple of (table_name, columns) where columns is list of dicts with:
        - name: column name
        - type: column type
        - constraints: any constraints (PRIMARY KEY, NOT NULL, etc.)
    """
    # Extract table name
    table_match = re.search(r"CREATE TABLE.*?(\w+)\s*\(", sql, re.IGNORECASE)
    if not table_match:
        return "", []

    table_name = table_match.group(1)

    # Extract column definitions
    columns = []
    # Split by commas not inside parentheses
    col_section = sql[sql.index("(") + 1 : sql.rindex(")")]

    # Handle constraints that span multiple lines
    lines = [line.strip() for line in col_section.split("\n") if line.strip()]

    for line in lines:
        # Skip table-level constraints like PRIMARY KEY (month, category)
        if line.upper().startswith(("PRIMARY KEY (", "FOREIGN KEY", "UNIQUE (", "CHECK (")):
            continue

        # Parse column definition
        parts = line.split()
        if len(parts) >= 2:
            col_name = parts[0]
            col_type = parts[1].rstrip(",")
            constraints = " ".join(parts[2:]).replace(",", "").strip()

            columns.append({"name": col_name, "type": col_type, "constraints": constraints})

    return table_name, columns


def generate_table_doc(table_name: str, columns: list[dict[str, str]], description: str) -> str:
    """Generate markdown documentation for a table."""
    lines = [
        f"### {table_name}",
        "",
        description,
        "",
        "| Column | Type | Constraints | Description |",
        "|--------|------|-------------|-------------|",
    ]

    # Column descriptions
    col_descriptions = {
        # categories
        "id": "Unique identifier",
        "name": "Category name",
        # transactions
        "date": "Transaction date (YYYY-MM-DD)",
        "description": "Transaction description/merchant name",
        "amount": "Amount in pence (negative for expenses)",
        "category": "Category name (NULL if unreviewed)",
        "reviewed": "Whether transaction has been categorized (0 or 1)",
        "ignored": "Whether transaction is excluded from reports (0 or 1)",
        # auto_allocate_rules
        # auto_ignore_rules - description is the primary key
        # budgets
        "month": "Month identifier (YYYY-MM)",
        # monthly_tbb
    }

    for col in columns:
        desc = col_descriptions.get(col["name"], "")
        if col["name"] == "amount" and table_name in ("budgets", "monthly_tbb"):
            desc = "Amount in pence"
        if col["name"] == "category" and table_name == "budgets":
            desc = "Category name"
        if col["name"] == "category" and table_name == "auto_allocate_rules":
            desc = "Category to automatically assign"
        if col["name"] == "description" and table_name in ("auto_allocate_rules", "auto_ignore_rules"):
            desc = "Transaction description pattern to match"

        constraints = col["constraints"] or "—"
        lines.append(f"| {col['name']} | {col['type']} | {constraints} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def generate_schema_reference() -> str:
    """Generate complete schema reference documentation."""
    # Create a temporary database to extract schema
    temp_db = Path("/tmp/ynam_schema_temp.db")
    if temp_db.exists():
        temp_db.unlink()

    init_database(temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Get all table schemas
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables_sql = cursor.fetchall()

    # Indexes are hardcoded in the documentation section below
    # Could be extracted dynamically in the future if needed

    conn.close()
    temp_db.unlink()

    # Start building documentation
    lines = [
        "---",
        "tags: [reference]",
        "---",
        "",
        "# Database Schema Reference",
        "",
        "YNAM uses SQLite to store all data locally.",
        "",
        "## Database Location",
        "",
        "Default: `~/.ynam/ynam.db`",
        "",
        "## Tables",
        "",
    ]

    # Table descriptions
    table_descriptions = {
        "categories": "User-defined spending and income categories.",
        "transactions": "All imported financial transactions.",
        "auto_allocate_rules": "Rules for automatically categorizing transactions based on description.",
        "auto_ignore_rules": "Rules for automatically ignoring transactions (excluding from reports).",
        "budgets": "Monthly budget allocations by category.",
        "monthly_tbb": "To Be Budgeted (TBB) amount for each month.",
    }

    # Generate table documentation
    for sql_tuple in tables_sql:
        sql = sql_tuple[0]
        table_name, columns = parse_create_table(sql)
        if table_name:
            description = table_descriptions.get(table_name, "")
            lines.append(generate_table_doc(table_name, columns, description))

    # Add indexes section
    lines.extend(
        [
            "## Indexes",
            "",
            "Performance indexes on common query patterns:",
            "",
            "- `idx_txn_date`: Index on transactions(date) for date range queries",
            "- `idx_txn_category_date`: Index on transactions(category, date) for category reports",
            "- `idx_txn_desc_reviewed`: Index on transactions(description, reviewed) for review workflow",
            "",
        ]
    )

    # Add currency section
    lines.extend(
        [
            "## Currency Storage",
            "",
            "All monetary amounts are stored as integers representing pence to prevent floating-point precision errors.",
            "",
            "Examples:",
            "- £10.50 is stored as 1050",
            "- £100.00 is stored as 10000",
            "- -£42.99 (expense) is stored as -4299",
            "",
        ]
    )

    # Add notes
    lines.extend(
        [
            "## Notes",
            "",
            "- The `ignored` column was added in a migration. Older databases are automatically updated on first run.",
            "- Transactions with `ignored=1` are excluded from all spending reports and budget calculations.",
            "- Auto-allocate rules match on exact description. Future versions may support pattern matching.",
            "- Budget amounts and TBB are always positive integers in pence.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Generate and write schema reference documentation."""
    output_path = Path(__file__).parent.parent / "docs" / "reference" / "database-schema.md"

    doc = generate_schema_reference()

    output_path.write_text(doc)
    print(f"Generated schema reference at {output_path}")


if __name__ == "__main__":
    main()
