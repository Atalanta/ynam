---
tags: [reference]
---

# Database Schema Reference

YNAM uses SQLite to store all data locally.

## Database Location

Default: `~/.ynam/ynam.db`

## Tables

### categories

User-defined spending and income categories.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique identifier |
| name | TEXT | NOT NULL UNIQUE | Category name |

### transactions

All imported financial transactions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique identifier |
| date | TEXT | NOT NULL | Transaction date (YYYY-MM-DD) |
| description | TEXT | NOT NULL | Transaction description/merchant name |
| amount | INTEGER | NOT NULL | Amount in pence (negative for expenses) |
| category | TEXT | — | Category name (NULL if unreviewed) |
| reviewed | INTEGER | NOT NULL DEFAULT 0 | Whether transaction has been categorized (0 or 1) |
| ignored | INTEGER | NOT NULL DEFAULT 0 | Whether transaction is excluded from reports (0 or 1) |

### auto_allocate_rules

Rules for automatically categorizing transactions based on description.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| description | TEXT | PRIMARY KEY | Transaction description pattern to match |
| category | TEXT | NOT NULL | Category to automatically assign |

### auto_ignore_rules

Rules for automatically ignoring transactions (excluding from reports).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| description | TEXT | PRIMARY KEY | Transaction description pattern to match |

### budgets

Monthly budget allocations by category.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| month | TEXT | NOT NULL | Month identifier (YYYY-MM) |
| category | TEXT | NOT NULL | Category name |
| amount | INTEGER | NOT NULL | Amount in pence |

### monthly_tbb

To Be Budgeted (TBB) amount for each month.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| month | TEXT | PRIMARY KEY | Month identifier (YYYY-MM) |
| amount | INTEGER | NOT NULL | Amount in pence |

## Indexes

Performance indexes on common query patterns:

- `idx_txn_date`: Index on transactions(date) for date range queries
- `idx_txn_category_date`: Index on transactions(category, date) for category reports
- `idx_txn_desc_reviewed`: Index on transactions(description, reviewed) for review workflow

## Currency Storage

All monetary amounts are stored as integers representing pence to prevent floating-point precision errors.

Examples:
- £10.50 is stored as 1050
- £100.00 is stored as 10000
- -£42.99 (expense) is stored as -4299

## Notes

- The `ignored` column was added in a migration. Older databases are automatically updated on first run.
- Transactions with `ignored=1` are excluded from all spending reports and budget calculations.
- Auto-allocate rules match on exact description. Future versions may support pattern matching.
- Budget amounts and TBB are always positive integers in pence.
