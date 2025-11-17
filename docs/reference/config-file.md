---
tags: [reference]
---

# Configuration file reference

Complete reference for the ynam configuration file.

## File location

`~/.ynam/config.toml`

## File permissions

The config file is automatically created with mode 600 (owner read/write only) for security.

## Schema

```toml
# Array of data sources
sources = [
    # ... source configurations
]
```

## Source types

### API source

```toml
[[sources]]
name = "string"           # Unique identifier for this source
type = "api"              # Source type
provider = "starling"     # API provider (currently only "starling" supported)
token = "string"          # (Optional) API token - alternatively use token_env
token_env = "ENV_VAR"     # (Optional) Environment variable containing token
days = 30                 # (Optional) Initial fetch window in days (default: 30)
```

**Token resolution:**
1. If `token_env` is specified, reads from that environment variable
2. If `token` is specified, uses that value directly
3. If neither found, command fails with error

### CSV source

```toml
[[sources]]
name = "string"                    # Unique identifier for this source
type = "csv"                       # Source type
path = "~/path/to/file.csv"        # Path to CSV file (~ expands to home directory)
date_column = "string"             # Column name containing transaction date
description_column = "string"      # Column name containing description/merchant
amount_column = "string"           # Column name containing amount (converted to negative for expenses)
```

**Column mappings:**
- If column mappings are incomplete or missing, sync will run interactive analyzer
- Interactive analyzer detects columns and prompts for confirmation
- Confirmed mappings are saved back to config file

## Example configuration

```toml
# Multiple sources configured
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token_env = "STARLING_TOKEN"
days = 90

[[sources]]
name = "capital-one"
type = "csv"
path = "~/Downloads/transactions.csv"
date_column = "date"
description_column = "merchant.name"
amount_column = "amount"

[[sources]]
name = "virgin"
type = "csv"
path = "~/Downloads/virgin-money.csv"
date_column = "Transaction Date"
description_column = "Merchant"
amount_column = "Amount"
```

## Security considerations

- Config file is created with 600 permissions (owner only)
- API tokens can be stored directly or referenced via environment variables
- Environment variables preferred for security-sensitive deployments
- CSV paths use standard path expansion (~, environment variables)

## Validation

The config file is validated when loading sources:
- Source names must be unique
- Required fields must be present for each source type
- File paths are validated when syncing

## Future extensions

Additional source types may be added:
- `ofx` - OFX/QFX file import
- `api` providers - Monzo, Revolut, etc.
- `database` - Direct database connections
