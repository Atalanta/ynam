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

Creates a new SQLite database at `~/.ynam/ynam.db` with the required schema for managing transactions.

**Exit codes:**

- 0: Success
- 1: Database or filesystem error

### fetch

Fetch transactions from Starling Bank API.

**Usage:**

```bash
export STARLING_TOKEN="your-token-here"
uv run ynam fetch
```

**Arguments:** None

**Options:** None

**Environment variables:**

- `STARLING_TOKEN` (required): OAuth bearer token for Starling Bank API

**Description:**

Fetches transactions from the Starling Bank API and inserts them into the local database.

**Exit codes:**

- 0: Success
- 1: API error, database error, or missing token
