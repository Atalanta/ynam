---
tags: [how-to]
---

# How to configure data sources

Configure sources in your config file to sync transactions from different providers.

## Prerequisites

- Initialized ynam (see [initialize the database](initialize-database.md))

## Config file location

`~/.ynam/config.toml`

The config file is created with secure permissions (600 - owner read/write only) when you run `ynam init`.

## Security note

Your API tokens are stored in the config file with restricted permissions. Keep this file secure.

For enhanced security, you can use environment variables instead of storing tokens directly in the config.

## API sources

### Starling Bank

```toml
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token_env = "STARLING_TOKEN"  # Read from environment variable
days = 90  # Initial fetch window (default: 30)
```

Or with token directly in config:

```toml
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token = "your-actual-token-here"
days = 90
```

**Token precedence:** Environment variable > Config file > Prompt

## CSV sources

### Basic CSV configuration

```toml
[[sources]]
name = "capital-one"
type = "csv"
path = "~/Downloads/transactions.csv"
date_column = "date"
description_column = "merchant.name"
amount_column = "amount"
direction_column = "debitCreditCode"
```

### Column mappings

- `date_column`: Column containing transaction date (ISO format preferred)
- `description_column`: Column containing merchant/payee name
- `amount_column`: Column containing amount (will be converted to pence/cents)
- `direction_column`: (Optional) Column indicating debit/credit or in/out

**Note:** If direction_column is omitted, amounts are assumed to be signed (negative for expenses).

### Interactive setup

If you don't specify column mappings, ynam will:
1. Analyze the CSV structure
2. Suggest column mappings
3. Show sample data
4. Prompt for confirmation
5. Save the mapping to your config file

This makes it easy to add new CSV sources without manually inspecting the file format.

## Multiple sources

You can configure multiple sources and sync them independently:

```toml
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token_env = "STARLING_TOKEN"

[[sources]]
name = "capital-one"
type = "csv"
path = "~/Downloads/capital-one.csv"
date_column = "date"
description_column = "merchant.name"
amount_column = "amount"
direction_column = "debitCreditCode"

[[sources]]
name = "virgin"
type = "csv"
path = "~/Downloads/virgin.csv"
date_column = "Transaction Date"
description_column = "Merchant"
amount_column = "Amount"
# No direction_column - amounts are signed
```

## Syncing from sources

Once configured, sync transactions:

```bash
# Sync from specific source
ynam sync starling
ynam sync capital-one

# View available sources (when sync fails)
ynam sync unknown-source
```

## Next steps

After syncing transactions, you can:
- View them with `ynam list`
- Categorize them with `ynam review`
- Analyze spending with `ynam report`
