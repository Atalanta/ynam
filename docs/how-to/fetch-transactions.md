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

3. Verify transactions were imported:

   ```bash
   sqlite3 ~/.ynam/ynam.db "SELECT COUNT(*) FROM transactions"
   ```

## Expected outcome

You will see messages showing:
- Account information being fetched
- Transactions being retrieved
- Number of transactions inserted

All fetched transactions will be stored in your local database.

## Next steps

After fetching transactions, you can review and categorize them using other ynam commands.
