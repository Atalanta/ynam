---
tags: [reference]
---

# CLI commands

Command-line interface reference for ynam.

## Usage

```bash
uv run ynam [COMMAND] [OPTIONS]
```

## Global options

| Option | Description |
|--------|-------------|
| --help | Show help message and exit |

## Commands

### init

Initialize ynam database and configuration.

**Usage:**

```bash
uv run ynam init
```

**Arguments:** None

**Options:** None

**Description:**

Creates a new SQLite database at `~/.ynam/ynam.db` and configuration file at `~/.ynam/config.toml` with secure permissions (600).

**Exit codes:**

- 0: Success
- 1: Database or filesystem error

### sync

Sync transactions from a configured source.

**Usage:**

```bash
uv run ynam sync SOURCE_NAME
```

**Arguments:**

- `SOURCE_NAME` (required): Name of the source configured in config.toml

**Options:** None

**Description:**

Syncs transactions from the specified source (API or CSV). Sources must be configured in `~/.ynam/config.toml`.

For API sources, automatically fetches from the most recent transaction date. For CSV sources, runs interactive column mapping if not already configured.

**Exit codes:**

- 0: Success
- 1: API error, database error, missing source, or file not found

**Examples:**

```bash
uv run ynam sync starling
uv run ynam sync capital-one
```

### list

List transactions.

**Usage:**

```bash
uv run ynam list [OPTIONS]
```

**Arguments:** None

**Options:**

- `--limit INTEGER`: Maximum number of transactions to show (default: 50)
- `--all, -a`: Show all transactions

**Description:**

Displays transactions in a table with date, description, amount, category, and reviewed status. Transactions are ordered by date descending (newest first).

**Exit codes:**

- 0: Success
- 1: Database error

**Examples:**

```bash
uv run ynam list              # Show 50 most recent
uv run ynam list --limit 20   # Show 20 most recent
uv run ynam list -a           # Show all transactions
```

### review

Review and categorize unreviewed transactions.

**Usage:**

```bash
uv run ynam review
```

**Arguments:** None

**Options:** None

**Description:**

Interactive command that loops through unreviewed transactions and prompts for categorization. Features:

- Smart category suggestions based on transaction history
- Press Enter to accept suggestion
- Press 'a' to auto-allocate all matching transactions (persists)
- Press 's' to skip (with option to skip all similar in session)
- Press 'q' to quit
- Press 'n' to create new category

**Exit codes:**

- 0: Success
- 1: Database error

### report

Generate income and spending breakdown report.

**Usage:**

```bash
uv run ynam report [OPTIONS]
```

**Arguments:** None

**Options:**

- `--sort-by TEXT`: Sort by 'value' or 'alpha' (default: value)
- `--histogram/--no-histogram`: Show histogram visualization (default: True)

**Description:**

Displays spending analysis with:
- Expenses breakdown by category (red, with bars)
- Income breakdown by category (green, with bars)
- Total expenses, total income, and net

**Exit codes:**

- 0: Success
- 1: Database error

**Examples:**

```bash
uv run ynam report                  # Default view
uv run ynam report --sort-by alpha  # Alphabetical order
uv run ynam report --no-histogram   # No bars, just numbers
```
