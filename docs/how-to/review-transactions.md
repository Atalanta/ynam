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
   - If categories exist, you'll see a numbered list of existing categories
   - Enter the number to select that category
   - Enter 'n' to create a new category
   - Enter 's' to skip this transaction

3. When creating a new category, enter the category name when prompted.

4. Press Enter after each selection.

## Expected outcome

Each reviewed transaction will be marked with the selected category and flagged as reviewed. Skipped transactions remain unreviewed and will appear again on the next run.

New categories are added to the database and will appear as options for future transactions.

## Next steps

After reviewing transactions, you can query the database to analyze spending by category.
