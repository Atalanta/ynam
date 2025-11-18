---
tags: [reference]
---

# CLI Commands Reference

Complete reference for all ynam CLI commands and options.

## Usage

```bash
uv run ynam [COMMAND] [OPTIONS]
```

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Commands

### backup

Backup your database and configuration files.

**Usage:**

```bash
uv run ynam backup
```

**Options:**

- `--output`, `-o`: Backup directory (default: ~/.ynam/backups)


### budget

Set your budget amounts for categories.

**Usage:**

```bash
uv run ynam budget
```

**Options:**

- `--set-tbb`: Set your To Be Budgeted amount for the month (in £)
- `--status`: Show your budget status and spending
- `--adjust`: Adjust your budget allocations interactively
- `--copy-from`: Copy budget from month (YYYY-MM), rolling over unspent amounts
- `--from`: Source category (name, index, or 'TBB')
- `--to`: Target category (name, index, or 'TBB')
- `--amount`: Amount to transfer (in £)
- `--month`: Month to budget for (YYYY-MM)


### init

Initialize ynam database and configuration.

**Usage:**

```bash
uv run ynam init
```

**Options:**

- `--force`, `-f`: Overwrite existing database and config


### inspect

Inspect your transactions for a specific category.

**Usage:**

```bash
uv run ynam inspect
```

**Arguments:**

- `CATEGORY` (required)

**Options:**

- `--all`, `-a`: Show all time
- `--month`: Specific month (YYYY-MM)


### list

List your transactions.

**Usage:**

```bash
uv run ynam list
```

**Options:**

- `--limit`: Maximum transactions to show (default: 50)
- `--all`, `-a`: Show all your transactions


### report

Show your income and spending breakdown.

**Usage:**

```bash
uv run ynam report
```

**Options:**

- `--sort-by`: Sort by 'value' or 'alpha' (default: value)
- `--histogram`: Show histogram of your spending (default: True)
- `--all`, `-a`: Show all time
- `--month`: Specific month (YYYY-MM)


### review

Review and categorize unreviewed transactions.

**Usage:**

```bash
uv run ynam review
```

**Options:**

- `--oldest-first`: Review oldest transactions first (default: newest first)


### sync

Sync your transactions from a configured source or CSV file.

**Usage:**

```bash
uv run ynam sync
```

**Arguments:**

- `SOURCE_NAME_OR_PATH` (required)

**Options:**

- `--days`: Days to fetch (overrides config)
- `--verbose`, `-v`: Show detailed duplicate report
