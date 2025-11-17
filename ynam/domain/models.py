"""Domain type definitions for ynam.

These NewTypes provide semantic clarity and help with type checking:
- Money: Amount in pence (minor units)
- Month: Month in YYYY-MM format
- CategoryName: Name of a budget category
- Description: Transaction description text
"""

from typing import NewType

# Money amounts are stored as pence (minor units) to avoid floating point errors
Money = NewType("Money", int)

# Month is always in YYYY-MM format (e.g., "2025-01")
Month = NewType("Month", str)

# Category name for budget categories
CategoryName = NewType("CategoryName", str)

# Transaction description text
Description = NewType("Description", str)
