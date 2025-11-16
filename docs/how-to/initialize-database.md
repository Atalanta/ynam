---
tags: [how-to]
---

# How to initialize the database

Initialize the ynam database to start tracking your finances.

## Prerequisites

You must have installed ynam dependencies with `uv sync`.

## Steps

1. Run the initialization command:

   ```bash
   uv run ynam initdb
   ```

2. Verify the database was created:

   ```bash
   ls ~/.ynam/ynam.db
   ```

## Expected outcome

You will see the message "Database initialized successfully!" and the database file will be created at `~/.ynam/ynam.db`.

## Next steps

After initializing the database, you can begin adding accounts and transactions.
