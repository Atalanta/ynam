---
tags: [how-to]
---

# How to view your spending report

Analyze your income and expenses with a visual breakdown by category.

## Prerequisites

- Categorized transactions (see [review transactions](review-transactions.md))

## Steps

1. View the current month's report:

   ```bash
   uv run ynam report
   ```

2. For a specific month:

   ```bash
   uv run ynam report --month 2025-10
   ```

3. For all time:

   ```bash
   uv run ynam report --all
   ```

## Expected outcome

YNAM displays:
- **Expenses by category** with amounts, budgets, and usage percentages
- Visual histogram bars showing relative spending
- **Income by category** with totals
- **Net** (income minus expenses)

Example output:

```
November 2025

Expenses by category:

  Groceries            £342.50 / £400.00 (86%)  ████████████████████
  Transport            £145.00 / £150.00 (97%)  ██████████████████
  Eating Out           £89.32                   ████████

  Total expenses: £576.82 / £550.00

Income by category:

  Salary               £2,500.00  ██████████████████████████████

  Total income: £2,500.00

Net: £1,923.18
```

## Options

- `--sort-by alpha`: Sort categories alphabetically instead of by value
- `--no-histogram`: Hide the visual bars
- `--month YYYY-MM`: Specific month
- `--all`: All time instead of current month

## Next steps

- Inspect specific categories with `ynam inspect <category>`
- Adjust your budget with `ynam budget --adjust`
