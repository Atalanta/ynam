"""Tests for ynam.dates pure functions."""

import pytest

from ynam.dates import month_range
from ynam.domain.models import Month


class TestMonthRange:
    """Tests for month_range."""

    def test_january_range(self) -> None:
        """Should calculate range for January."""
        since, until, label = month_range(Month("2025-01"))

        assert since == "2025-01-01"
        assert until == "2025-02-01"
        assert label == "January 2025"

    def test_december_range_crosses_year(self) -> None:
        """Should handle December (crosses year boundary)."""
        since, until, label = month_range(Month("2025-12"))

        assert since == "2025-12-01"
        assert until == "2026-01-01"
        assert label == "December 2025"

    def test_february_non_leap_year(self) -> None:
        """Should handle February in non-leap year."""
        since, until, label = month_range(Month("2025-02"))

        assert since == "2025-02-01"
        assert until == "2025-03-01"  # 28 days in Feb 2025
        assert label == "February 2025"

    def test_february_leap_year(self) -> None:
        """Should handle February in leap year."""
        since, until, label = month_range(Month("2024-02"))

        assert since == "2024-02-01"
        assert until == "2024-03-01"  # 29 days in Feb 2024
        assert label == "February 2024"

    def test_thirty_day_month(self) -> None:
        """Should handle 30-day months."""
        since, until, label = month_range(Month("2025-04"))

        assert since == "2025-04-01"
        assert until == "2025-05-01"
        assert label == "April 2025"

    def test_thirty_one_day_month(self) -> None:
        """Should handle 31-day months."""
        since, until, label = month_range(Month("2025-03"))

        assert since == "2025-03-01"
        assert until == "2025-04-01"
        assert label == "March 2025"

    def test_all_months_of_year(self) -> None:
        """Should correctly handle all 12 months."""
        expected = [
            ("2025-01-01", "2025-02-01", "January 2025"),
            ("2025-02-01", "2025-03-01", "February 2025"),
            ("2025-03-01", "2025-04-01", "March 2025"),
            ("2025-04-01", "2025-05-01", "April 2025"),
            ("2025-05-01", "2025-06-01", "May 2025"),
            ("2025-06-01", "2025-07-01", "June 2025"),
            ("2025-07-01", "2025-08-01", "July 2025"),
            ("2025-08-01", "2025-09-01", "August 2025"),
            ("2025-09-01", "2025-10-01", "September 2025"),
            ("2025-10-01", "2025-11-01", "October 2025"),
            ("2025-11-01", "2025-12-01", "November 2025"),
            ("2025-12-01", "2026-01-01", "December 2025"),
        ]

        for month_num in range(1, 13):
            month_str = f"2025-{month_num:02d}"
            result = month_range(Month(month_str))
            assert result == expected[month_num - 1]

    def test_invalid_month_format_raises_valueerror(self) -> None:
        """Should raise ValueError for invalid month format."""
        with pytest.raises(ValueError):
            month_range(Month("invalid"))

    def test_invalid_month_number_raises_valueerror(self) -> None:
        """Should raise ValueError for invalid month number."""
        with pytest.raises(ValueError):
            month_range(Month("2025-13"))
