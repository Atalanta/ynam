"""Pure functions for report calculations and aggregations.

This module contains the functional core for reporting operations:
- No I/O operations (no database, no console, no files)
- No side effects
- Pure data transformations
- Easy to test

All monetary amounts are in pence (Money type).
"""

from dataclasses import dataclass

from ynam.domain.models import CategoryName, Money


@dataclass(frozen=True)
class CategoryReport:
    """Immutable category report data."""

    category: CategoryName
    amount: Money
    budget: Money | None = None
    percentage: float | None = None


@dataclass(frozen=True)
class ExpenseReport:
    """Immutable expense report data."""

    categories: list[CategoryReport]
    total: Money
    total_budget: Money


@dataclass(frozen=True)
class IncomeReport:
    """Immutable income report data."""

    categories: list[CategoryReport]
    total: Money


@dataclass(frozen=True)
class FullReport:
    """Immutable full report with expenses, income, and net."""

    expenses: ExpenseReport
    income: IncomeReport
    net: Money


def calculate_budget_percentage(actual: Money, budget: Money) -> float:
    """Calculate percentage of budget used.

    Args:
        actual: Actual amount spent in pence.
        budget: Budget amount in pence.

    Returns:
        Percentage of budget used (0-100+).
    """
    if budget <= 0:
        return 0.0
    return (abs(actual) / budget) * 100


def create_category_report(
    category: CategoryName,
    amount: Money,
    budget: Money | None = None,
) -> CategoryReport:
    """Create category report with budget comparison.

    Args:
        category: Category name.
        amount: Amount in pence (negative for expenses, positive for income).
        budget: Optional budget amount in pence.

    Returns:
        CategoryReport with calculations.
    """
    percentage = None
    if budget is not None and budget > 0:
        percentage = calculate_budget_percentage(amount, budget)

    return CategoryReport(
        category=category,
        amount=amount,
        budget=budget,
        percentage=percentage,
    )


def split_expenses_and_income(
    breakdown: dict[CategoryName, Money],
) -> tuple[dict[CategoryName, Money], dict[CategoryName, Money]]:
    """Split category breakdown into expenses and income.

    Args:
        breakdown: Dictionary of category amounts (negative = expense, positive = income).

    Returns:
        Tuple of (expenses_dict, income_dict).
    """
    expenses = {cat: amt for cat, amt in breakdown.items() if amt < 0}
    income = {cat: amt for cat, amt in breakdown.items() if amt > 0}
    return expenses, income


def sort_expenses(
    expenses: dict[CategoryName, Money],
    sort_by: str = "value",
) -> list[tuple[CategoryName, Money]]:
    """Sort expenses by value or alphabetically.

    Args:
        expenses: Dictionary of expense categories and amounts.
        sort_by: Sort method - "value" or "alpha".

    Returns:
        Sorted list of (category, amount) tuples.
    """
    if sort_by == "alpha":
        return sorted(expenses.items(), key=lambda x: x[0])
    else:
        return sorted(expenses.items(), key=lambda x: x[1])


def sort_income(
    income: dict[CategoryName, Money],
    sort_by: str = "value",
) -> list[tuple[CategoryName, Money]]:
    """Sort income by value or alphabetically.

    Args:
        income: Dictionary of income categories and amounts.
        sort_by: Sort method - "value" or "alpha".

    Returns:
        Sorted list of (category, amount) tuples.
    """
    if sort_by == "alpha":
        return sorted(income.items(), key=lambda x: x[0])
    else:
        return sorted(income.items(), key=lambda x: x[1], reverse=True)


def create_expense_report(
    expenses: dict[CategoryName, Money],
    budgets: dict[CategoryName, Money],
    sort_by: str = "value",
) -> ExpenseReport:
    """Create expense report with budget comparisons.

    Args:
        expenses: Dictionary of expense categories and amounts (negative values).
        budgets: Dictionary of budget allocations.
        sort_by: Sort method - "value" or "alpha".

    Returns:
        ExpenseReport with sorted categories and totals.
    """
    sorted_expenses = sort_expenses(expenses, sort_by)

    categories = [create_category_report(cat, amt, budgets.get(cat)) for cat, amt in sorted_expenses]

    total = Money(sum(expenses.values()))
    total_budget = Money(sum(budgets.get(cat, Money(0)) for cat in expenses.keys()))

    return ExpenseReport(
        categories=categories,
        total=total,
        total_budget=total_budget,
    )


def create_income_report(
    income: dict[CategoryName, Money],
    sort_by: str = "value",
) -> IncomeReport:
    """Create income report.

    Args:
        income: Dictionary of income categories and amounts (positive values).
        sort_by: Sort method - "value" or "alpha".

    Returns:
        IncomeReport with sorted categories and total.
    """
    sorted_income = sort_income(income, sort_by)

    categories = [create_category_report(cat, amt) for cat, amt in sorted_income]

    total = Money(sum(income.values()))

    return IncomeReport(
        categories=categories,
        total=total,
    )


def create_full_report(
    breakdown: dict[CategoryName, Money],
    budgets: dict[CategoryName, Money],
    sort_by: str = "value",
) -> FullReport:
    """Create full report with expenses, income, and net.

    Args:
        breakdown: Dictionary of all category amounts.
        budgets: Dictionary of budget allocations.
        sort_by: Sort method - "value" or "alpha".

    Returns:
        FullReport with all calculations.
    """
    expenses_dict, income_dict = split_expenses_and_income(breakdown)

    expense_report = create_expense_report(expenses_dict, budgets, sort_by)
    income_report = create_income_report(income_dict, sort_by)

    net = Money(sum(breakdown.values()))

    return FullReport(
        expenses=expense_report,
        income=income_report,
        net=net,
    )


def calculate_histogram_bar_length(
    amount: Money,
    max_amount: Money,
    bar_width: int,
) -> int:
    """Calculate histogram bar length.

    Args:
        amount: Amount to display.
        max_amount: Maximum amount in dataset.
        bar_width: Maximum bar width in characters.

    Returns:
        Bar length in characters.
    """
    if max_amount <= 0:
        return 0
    return int((abs(amount) / max_amount) * bar_width)
