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

2. For each transaction, YNAM shows:
   - Transaction date, description, and amount
   - Numbered list of existing categories
   - Suggested category (if available from previous similar transactions)

3. Choose how to categorize:
   - **Press Enter** to accept the suggested category
   - **Enter a number** to select a different category
   - **Enter 'n'** to create a new category
   - **Enter 'a'** to auto-allocate all future transactions matching this description
   - **Enter 's'** to skip this transaction for now
   - **Enter 'i'** to ignore this transaction (excluded from reports)
   - **Enter 'q'** to quit review session

## Expected outcome

YNAM marks each reviewed transaction with your selected category. Skip keeps the transaction unreviewed for the next run.

Auto-allocated transactions are automatically categorized in future syncs. Ignored transactions are excluded from all spending reports (useful for transfers, payments between accounts, etc.).

YNAM adds new categories to the database and shows them as options for future transactions.

## Next steps

After reviewing transactions, you can query the database to analyze spending by category.
