---
tags: [how-to]
---

# How to set your monthly budget

Allocate your income across spending categories for the month.

## Prerequisites

- Categorized transactions (see [review transactions](review-transactions.md))
- Knowledge of how much you have available to budget this month

## Steps

1. Set your To Be Budgeted amount for the month:

   ```bash
   uv run ynam budget --set-tbb 2500
   ```

   Replace `2500` with your actual amount in pounds.

2. Run the interactive budget allocation:

   ```bash
   uv run ynam budget
   ```

3. For each category, YNAM shows:
   - Current budget allocation
   - Last month's spending
   - Remaining To Be Budgeted

4. Enter the amount to allocate (in £) or press 's' to skip.

5. Continue until you've allocated all your TBB.

## Expected outcome

YNAM allocates your specified amounts to each category and tracks remaining TBB. When you allocate all available money, your TBB reaches zero.

## Tips

- Base allocations on last month's actual spending
- Leave some unallocated for unexpected expenses
- You can adjust allocations later with `ynam budget --adjust`

## Next steps

- View your budget status with `ynam budget --status`
- Adjust allocations between categories as needed
- Run `ynam report` to compare spending against budget
