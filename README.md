# ynam - You Need A Mirror

Track your money with a YNAB-inspired budget tool that syncs with Starling Bank.

## Features

- Initialize local SQLite database for transaction storage
- Fetch transactions from Starling Bank API
- Review and categorize transactions (fixed/variable, mandatory/discretionary)
- View account balance and spending breakdown by category

## Quick start

Install dependencies:

```bash
uv sync
```

Initialize the database:

```bash
uv run ynam initdb
```

Fetch transactions from Starling Bank:

```bash
export STARLING_TOKEN="your-oauth-token"
uv run ynam fetch
```

## Documentation

- [How-to guides](docs/how-to/README.md) - Practical guides for common tasks
- [Reference](docs/reference/README.md) - Technical specifications and API details

## Development

Run tests:

```bash
uv run pytest
```
