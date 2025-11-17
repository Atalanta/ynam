---
tags: [how-to]
---

# How to inspect a category's transactions

View all transactions for a specific category to understand spending patterns.

## Prerequisites

- Categorized transactions (see [review transactions](review-transactions.md))

## Steps

1. Inspect a category for the current month:

   ```bash
   uv run ynam inspect Groceries
   ```

2. For a specific month:

   ```bash
   uv run ynam inspect Groceries --month 2025-10
   ```

3. For all time:

   ```bash
   uv run ynam inspect Groceries --all
   ```

## Expected outcome

YNAM displays a table showing:
- Date of each transaction
- Description
- Amount
- Running total for the category

Example output:

```
Groceries - November 2025 (15 transactions)

┌───┬────────────┬─────────────────────────┬──────────┐
│ # │ Date       │ Description             │   Amount │
├───┼────────────┼─────────────────────────┼──────────┤
│ 1 │ 2025-11-15 │ Tesco Store             │  -£45.32 │
│ 2 │ 2025-11-12 │ Sainsbury's             │  -£67.20 │
│ 3 │ 2025-11-08 │ Aldi                    │  -£32.15 │
└───┴────────────┴─────────────────────────┴──────────┘

Total: -£342.50
```

After viewing, you can select a transaction by number to recategorize it if needed.

## Use cases

- Verify all transactions are correctly categorized
- Find specific transactions you want to recategorize
- Understand spending patterns within a category
- Review "Unreviewed" category to find missed transactions

## Tips

- Use `ynam inspect Unreviewed` to find transactions you haven't categorized yet
- Transaction numbers let you quickly recategorize mistakes
- Combine with `--month` to review specific periods

## Next steps

- Recategorize transactions directly from the inspect view
- Adjust budget allocations based on actual spending patterns
