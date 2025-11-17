---
tags: [how-to]
---

# How to sync transactions from Starling Bank

Import transactions from your Starling Bank account into ynam.

## Prerequisites

- Initialized ynam (see [initialize the database](initialize-database.md))
- Configured Starling source (see [configure sources](configure-sources.md))
- Starling Bank OAuth token

## Steps

1. Configure your Starling source in `~/.ynam/config.toml`:

   ```toml
   [[sources]]
   name = "starling"
   type = "api"
   provider = "starling"
   token_env = "STARLING_TOKEN"
   days = 90  # Initial fetch window
   ```

2. Set your Starling Bank OAuth token as an environment variable:

   ```bash
   export STARLING_TOKEN="your-oauth-token-here"
   ```

3. Run the sync command:

   ```bash
   uv run ynam sync starling
   ```

   The sync command automatically determines the date range:
   - If transactions exist in the database, it fetches all transactions since the most recent one
   - If the database is empty, it fetches the configured number of days (default: 30)

4. Verify transactions were imported:

   ```bash
   uv run ynam list
   ```

## Expected outcome

YNAM shows messages displaying:
- Syncing from Starling Bank API
- The date range it's fetching
- Number of transactions inserted

YNAM stores all synced transactions in your local database. Subsequent syncs retrieve only new transactions, avoiding duplicates.

## Next steps

After syncing transactions, you can:
- Review and categorize them with `ynam review`
- Analyze spending with `ynam report`
