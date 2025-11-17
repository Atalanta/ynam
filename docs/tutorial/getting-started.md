---
tags: [tutorial]
---

# Getting Started with YNAM

Learn zero-based budgeting by setting up your first month's budget.

## What you'll build

By the end of this tutorial, you'll have:
- A working YNAM installation with your transactions imported
- All transactions categorized
- A complete monthly budget with every pound allocated

## Prerequisites

- Python 3.11 or later
- uv package manager
- Access to your bank transactions (Starling API token or CSV export)

## Install YNAM

Clone and install dependencies:

```bash
git clone https://github.com/Atalanta/ynam.git
cd ynam
uv sync
```

## Initialize your database

Create the database and configuration file:

```bash
uv run ynam init
```

This creates:
- `~/.ynam/ynam.db` - SQLite database (600 permissions)
- `~/.ynam/config.toml` - Configuration file (600 permissions)

## Configure your bank connection

### Option A: Starling Bank API

Open `~/.ynam/config.toml` and add:

```toml
[[sources]]
name = "starling"
type = "api"
provider = "starling"
token_env = "STARLING_TOKEN"
days = 90
```

Set your token:

```bash
export STARLING_TOKEN="your-oauth-token-here"
```

### Option B: CSV file

If you have a CSV export from your bank:

```bash
uv run ynam sync ~/Downloads/transactions.csv
```

YNAM will detect the columns and prompt you to confirm which column contains the date, description, and amount.

## Import your transactions

Sync from Starling:

```bash
uv run ynam sync starling
```

Or sync from CSV (if not done in previous step):

```bash
uv run ynam sync ~/Downloads/transactions.csv
```

You'll see output like:

```
✓ Successfully synced 247 transactions!
Skipped 3 duplicates
```

## Review and categorize

Start the interactive review:

```bash
uv run ynam review
```

For each transaction, you'll see:

```
Date: 2025-11-15
Description: Tesco Store
Amount: -£45.32

Categories:
  1. Groceries
  2. Eating Out
  n. New category

Suggested: Groceries (press Enter to accept, a to auto-allocate all)

Select category (1-2, n for new, s to skip, i to ignore, q to quit):
```

Press Enter to accept the suggestion, or type a number to choose a different category.

**Tips:**
- Press `a` to auto-categorize all future transactions matching this description
- Press `i` to ignore transfers and payments (excluded from reports)
- Create categories as you go by pressing `n`

## Set your budget for the month

First, set how much you have to budget this month:

```bash
uv run ynam budget --set-tbb 2500
```

This sets your "To Be Budgeted" amount to £2,500.

Now allocate that money to categories:

```bash
uv run ynam budget
```

For each category, you'll see:

```
Groceries
  Current budget: not set
  November 2025 spending: £342.50
  Remaining TBB: £2,500.00

  Enter budget (in £, or 's' to skip):
```

Enter amounts for each category. Try to allocate all your TBB.

## View your spending report

See where your money went:

```bash
uv run ynam report
```

You'll see a breakdown like:

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

## What's next?

You've completed your first budget! Here's what to do regularly:

1. **Weekly**: Sync transactions and review new ones
2. **Monthly**: Set TBB, allocate to categories, review spending report
3. **As needed**: Adjust budget allocations with `ynam budget --adjust`

## Learn more

- [How-to guides](../how-to/README.md) - Specific tasks like adjusting budgets
- [Understanding Zero-Based Budgeting](../explanation/zero-based-budgeting.md) - Why allocate every pound
- [CLI Reference](../reference/cli-commands.md) - Complete command documentation
