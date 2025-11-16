---
tags: [how-to]
---

# How to review and categorize transactions

Categorize your transactions to track spending patterns.

## Prerequisites

- Transactions in the database (see [fetch transactions](fetch-transactions.md))

## Steps

1. Run the review command:

   ```bash
   uv run ynam review
   ```

2. For each transaction, review the details and select a category:
   - 1: fixed mandatory
   - 2: variable mandatory
   - 3: fixed discretionary
   - 4: variable discretionary
   - s: skip this transaction

3. Press Enter after each selection.

## Expected outcome

Each reviewed transaction will be marked with the selected category and flagged as reviewed. Skipped transactions remain unreviewed and will appear again on the next run.

## Next steps

After reviewing transactions, you can query the database to analyze spending by category.
