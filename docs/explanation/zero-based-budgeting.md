---
tags: [explanation]
---

# Understanding Zero-Based Budgeting

Zero-based budgeting means allocating all available money to categories before any spending happens.

## Core Idea

Traditional budgets track past spending. Zero-based budgeting assigns all available funds before any spending occurs. The goal is simple: allocate until the "to be budgeted" amount reaches zero.

## How It Works

1. Money arrives.
2. Allocate it to categories.
3. Spend from those categories.
4. Adjust allocations when priorities change.

Categories may represent bills, discretionary spending, savings goals, or future obligations.

## To Be Budgeted (TBB)

TBB shows unallocated money:

Income this month:           £2,500
Already budgeted:            £2,100
To Be Budgeted:              £400

Allocate the £400 to categories. TBB becomes zero. Zero means allocated, not spent.

## Category Rollover

Category balances persist across months. If you budget £200 for groceries and spend £180, the remaining £20 stays in the groceries category. Add whatever is required next month to reach the amount you want.

Unspent money remains where you put it until reallocated.

## How YNAM Applies This

YNAM adapts this budgeting method for UK banking and a CLI workflow.

UK banking considerations:
- Standing orders and Direct Debits cover most recurring bills.
- One primary current account is common.
- Debit cards are the dominant payment method.

CLI approach:
- Manual transaction imports from API sources or CSV exports.
- Local SQLite database; data stays on your machine.
- Terminal-based interaction for speed and scriptability.

Manual syncing avoids OAuth integrations and external infrastructure, keeping the tool local-first.

## User Responsibilities

Zero-based budgeting requires active engagement:

- Reviewing transactions
- Updating category allocations
- Maintaining accurate categorization

The tool reflects the allocations you make. It does not infer intent.

## Tool Limitations

- Categories and budgets are maintained manually.
- No automatic categorization beyond simple pattern matching.
- No built-in support for refunds or split transactions.
- No cross-device synchronization.

## Context

YNAB popularised zero-based budgeting. YNAM brings the same method to UK banking with a terminal-first design.
