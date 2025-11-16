# ynam - You Need A Mirror

Track your money with a YNAB-inspired budget tool. Sync transactions from multiple sources, categorize spending, and analyze your finances.

## Features

- **Multi-source sync** - Starling Bank API, CSV files (Capital One, Virgin Money, etc.)
- **Smart categorization** - Interactive review with auto-suggestions based on history
- **Spending analysis** - Visual reports with histograms, income vs expenses breakdown
- **Secure configuration** - TOML config with 600 permissions, environment variables for tokens
- **Local-first** - SQLite database, no cloud dependencies

## Quick start

Install dependencies:

```bash
uv sync
```

Initialize ynam:

```bash
uv run ynam init
```

Configure your data sources in `~/.ynam/config.toml`:

```toml
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token_env = "STARLING_TOKEN"
days = 90
```

Sync transactions:

```bash
export STARLING_TOKEN="your-oauth-token"
uv run ynam sync starling
```

Review and categorize:

```bash
uv run ynam review
```

View spending report:

```bash
uv run ynam report
```

## Documentation

- [How-to guides](docs/how-to/README.md) - Practical guides for common tasks
- [Reference](docs/reference/README.md) - Technical specifications and API details

## Development

Run tests:

```bash
uv run pytest
```
