---
tags: [how-to]
---

# How to fetch transactions from Starling Bank

Import transactions from your Starling Bank account into ynam.

## Prerequisites

- Initialized ynam database (see [initialize the database](initialize-database.md))
- Starling Bank OAuth token

## Steps

1. Set your Starling Bank OAuth token as an environment variable:

   ```bash
   export STARLING_TOKEN="your-oauth-token-here"
   ```

2. Run the fetch command:

   ```bash
   uv run ynam fetch
   ```

   The fetch command automatically determines the date range:
   - If transactions exist in the database, it fetches all transactions since the most recent one
   - If the database is empty, it fetches the last 30 days by default

3. For initial seeding with more history, use the `--days` option:

   ```bash
   uv run ynam fetch --days 90
   ```

4. Verify transactions were imported:

   ```bash
   sqlite3 ~/.ynam/ynam.db "SELECT COUNT(*) FROM transactions"
   ```

## Expected outcome

You will see messages showing:
- Account information being fetched
- The date range being fetched
- Transactions being retrieved
- Number of transactions inserted

All fetched transactions will be stored in your local database. Subsequent fetches will only retrieve new transactions, avoiding duplicates.

## Next steps

After fetching transactions, you can review and categorize them using other ynam commands.
