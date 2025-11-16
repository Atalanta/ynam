---
tags: [how-to]
---

# How to check account status

View your current balance and spending breakdown.

## Prerequisites

- Starling Bank OAuth token with `balance:read` permission
- Reviewed transactions in the database (see [review transactions](review-transactions.md))

## Steps

1. Set your Starling Bank OAuth token:

   ```bash
   export STARLING_TOKEN="your-oauth-token-here"
   ```

2. Run the status command:

   ```bash
   uv run ynam status
   ```

3. Review the output showing:
   - Current Starling account balance
   - Spending breakdown by category

## Expected outcome

You will see your current account balance from Starling Bank and spending totals for each category.

## Tips

- Spending breakdown only shows reviewed transactions
- Make sure your token has the `balance:read` permission enabled
