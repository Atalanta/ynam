---
tags: [reference]
---

# Database schema

ynam uses SQLite to store financial data locally.

## Database location

Default: `~/.ynam/ynam.db`

## Tables

### transactions

Financial transactions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique transaction identifier |
| date | TEXT | NOT NULL | Transaction date |
| description | TEXT | NOT NULL | Transaction description |
| amount | INTEGER | NOT NULL | Amount in cents |
| category | TEXT | | Transaction category |
| reviewed | INTEGER | NOT NULL DEFAULT 0 | Whether transaction has been reviewed (0 or 1) |

### Categories

Transactions can be categorized as:
- fixed mandatory
- variable mandatory
- fixed discretionary
- variable discretionary

## Currency storage

All monetary amounts are stored as integers representing cents (or pence). This prevents floating-point precision errors in financial calculations.

Examples:
- $10.50 is stored as 1050
- £100.00 is stored as 10000
