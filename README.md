# ynam - You Need A Mirror

Hold up a mirror to your spending habits, and make a plan to stay aligned with your values.

YNAB's zero-based budgeting concept, adapted for UK banking and CLI workflows. Built for people who prefer the terminal to the browser.

## Features

- **Multi-source sync** - Starling Bank API, CSV files (Capital One, Virgin Money, etc.)
- **Smart categorization** - Interactive review with auto-suggestions based on history
- **Zero-based budgeting** - Allocate every pound, roll over unspent amounts
- **Spending analysis** - Visual reports with histograms, income vs expenses breakdown
- **Local-first** - SQLite database, no cloud dependencies

## Get started

Initialize the database:

```bash
ynam init
```

Configure a source in `~/.config/ynam/config.toml`, then sync:

```bash
ynam sync your-source-name
```

Review and categorize transactions:

```bash
ynam review
```

## Documentation

- [CLI Reference](docs/reference/cli-commands.md) - Complete command documentation
- [Database Schema](docs/reference/database-schema.md) - Database structure and conventions

## Development

Run tests:

```bash
uv run pytest
```
