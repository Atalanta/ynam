---
tags: [reference]
---

# CLI commands

Command-line interface reference for ynam.

## Usage

```bash
uv run ynam [COMMAND]
```

## Global options

| Option | Description |
|--------|-------------|
| --help | Show help message and exit |

## Commands

### initdb

Initialize the ynam database.

**Usage:**

```bash
uv run ynam initdb
```

**Arguments:** None

**Options:** None

**Description:**

Creates a new SQLite database at `~/.ynam/ynam.db` with the required schema for managing accounts, transactions, budgets, and categories.

**Exit codes:**

- 0: Success
- 1: Database or filesystem error
