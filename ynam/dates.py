"""Date utilities for YNAM.

Pure functions for date range calculations and formatting.
"""

from datetime import datetime, timedelta

from ynam.domain.models import Month


def month_range(month: Month) -> tuple[str, str, str]:
    """Calculate date range and label for a month.

    Args:
        month: Month in YYYY-MM format.

    Returns:
        Tuple of (since_date, until_date, label) where:
        - since_date: First day of month (YYYY-MM-DD)
        - until_date: First day of next month (YYYY-MM-DD)
        - label: Human-readable month (e.g., "January 2025")
    """
    dt = datetime.strptime(month, "%Y-%m")
    since = dt.strftime("%Y-%m-01")
    next_month = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    until = next_month.strftime("%Y-%m-%d")
    label = dt.strftime("%B %Y")
    return since, until, label
