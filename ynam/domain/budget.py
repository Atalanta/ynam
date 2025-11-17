"""Pure functions for budget calculations and logic.

This module contains the functional core for budget operations:
- No I/O operations (no database, no console, no files)
- No side effects
- Pure data transformations
- Easy to test

All monetary amounts are in pence (Money type).
"""

from dataclasses import dataclass

from ynam.domain.models import CategoryName, Money


@dataclass(frozen=True)
class BudgetAllocation:
    """Immutable budget allocation for a category."""

    category: CategoryName
    allocated: Money


@dataclass(frozen=True)
class CategorySpending:
    """Immutable spending data for a category."""

    category: CategoryName
    spent: Money  # Negative for expenses, positive for income


@dataclass(frozen=True)
class CategoryRollover:
    """Immutable rollover data for a category."""

    category: CategoryName
    allocated: Money
    spent: Money
    available: Money


@dataclass(frozen=True)
class BudgetSummary:
    """Immutable budget summary."""

    tbb: Money
    total_allocated: Money
    remaining_tbb: Money
    allocations: dict[CategoryName, Money]


@dataclass(frozen=True)
class RolloverSummary:
    """Immutable rollover summary."""

    base_tbb: Money
    total_rollover: Money
    new_tbb: Money
    rollovers: list[CategoryRollover]
    allocations: dict[CategoryName, Money]


def calculate_remaining_tbb(tbb: Money, allocations: dict[CategoryName, Money]) -> Money:
    """Calculate remaining To Be Budgeted amount.

    Args:
        tbb: Total To Be Budgeted amount in pence.
        allocations: Dictionary of category allocations in pence.

    Returns:
        Remaining TBB in pence (can be negative if over-allocated).
    """
    total_allocated = sum(allocations.values())
    return Money(tbb - total_allocated)


def calculate_category_available(allocated: Money, spent: Money) -> Money:
    """Calculate available amount for a category.

    Args:
        allocated: Amount allocated to category in pence.
        spent: Amount spent in pence (negative for expenses, positive for income).

    Returns:
        Available amount in pence.
    """
    spent_abs = abs(spent) if spent < 0 else 0
    return Money(allocated - spent_abs)


def calculate_rollover(
    budgets: dict[CategoryName, Money],
    spending: dict[CategoryName, Money],
) -> list[CategoryRollover]:
    """Calculate rollover amounts for each category.

    Args:
        budgets: Dictionary of category budgets in pence.
        spending: Dictionary of category spending in pence (negative for expenses).

    Returns:
        List of CategoryRollover objects for categories with positive available amounts.
    """
    rollovers: list[CategoryRollover] = []

    for category, allocated in budgets.items():
        spent_pence = spending.get(category, Money(0))
        available = calculate_category_available(allocated, spent_pence)

        if available > 0:
            rollovers.append(
                CategoryRollover(
                    category=category,
                    allocated=allocated,
                    spent=spent_pence,
                    available=available,
                )
            )

    return rollovers


def calculate_rollover_summary(
    base_tbb: Money,
    budgets: dict[CategoryName, Money],
    spending: dict[CategoryName, Money],
) -> RolloverSummary:
    """Calculate complete rollover summary.

    Args:
        base_tbb: Base To Be Budgeted amount before rollover.
        budgets: Dictionary of category budgets in pence.
        spending: Dictionary of category spending in pence (negative for expenses).

    Returns:
        RolloverSummary with all rollover calculations.
    """
    rollovers = calculate_rollover(budgets, spending)
    total_rollover = Money(sum(r.available for r in rollovers))
    new_tbb = Money(base_tbb + total_rollover)

    return RolloverSummary(
        base_tbb=base_tbb,
        total_rollover=total_rollover,
        new_tbb=new_tbb,
        rollovers=rollovers,
        allocations=budgets,
    )


def validate_allocation_from_tbb(
    amount: Money,
    remaining_tbb: Money,
) -> tuple[bool, str | None]:
    """Validate allocation from TBB.

    Args:
        amount: Amount to allocate in pence.
        remaining_tbb: Remaining TBB in pence.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if amount <= 0:
        return False, "Amount must be positive"

    if amount > remaining_tbb:
        return False, f"Not enough TBB. Available: £{remaining_tbb / 100:,.2f}"

    return True, None


def validate_allocation_from_category(
    amount: Money,
    current_allocation: Money,
) -> tuple[bool, str | None]:
    """Validate removing allocation from category.

    Args:
        amount: Amount to remove in pence.
        current_allocation: Current allocation in pence.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if amount <= 0:
        return False, "Amount must be positive"

    if amount > current_allocation:
        return False, f"Not enough allocated. Available: £{current_allocation / 100:,.2f}"

    return True, None


def calculate_new_allocation(
    category: CategoryName,
    current: Money,
    change: Money,
    remaining_tbb: Money,
) -> tuple[Money, Money, str | None]:
    """Calculate new allocation after change.

    Args:
        category: Category name.
        current: Current allocation in pence.
        change: Change amount in pence (positive = add, negative = remove).
        remaining_tbb: Current remaining TBB in pence.

    Returns:
        Tuple of (new_allocation, new_remaining_tbb, error_message).
    """
    if change > 0:
        # Adding from TBB
        if change > remaining_tbb:
            return current, remaining_tbb, f"Not enough TBB. Available: £{remaining_tbb / 100:,.2f}"
        return Money(current + change), Money(remaining_tbb - change), None

    elif change < 0:
        # Removing to TBB
        if abs(change) > current:
            return current, remaining_tbb, f"Not enough allocated. Available: £{current / 100:,.2f}"
        return Money(current + change), Money(remaining_tbb - change), None

    else:
        # No change
        return current, remaining_tbb, None


def calculate_budget_transfer(
    from_category: CategoryName,
    to_category: CategoryName,
    amount: Money,
    from_current: Money,
    to_current: Money,
) -> tuple[Money, Money, str | None]:
    """Calculate budget transfer between categories.

    Args:
        from_category: Source category.
        to_category: Target category.
        amount: Amount to transfer in pence.
        from_current: Current allocation of source category in pence.
        to_current: Current allocation of target category in pence.

    Returns:
        Tuple of (new_from_allocation, new_to_allocation, error_message).
    """
    if amount <= 0:
        return from_current, to_current, "Amount must be positive"

    if amount > from_current:
        return (
            from_current,
            to_current,
            f"Not enough allocated in {from_category}. Available: £{from_current / 100:,.2f}",
        )

    return Money(from_current - amount), Money(to_current + amount), None


def create_budget_summary(
    tbb: Money,
    allocations: dict[CategoryName, Money],
) -> BudgetSummary:
    """Create budget summary with calculations.

    Args:
        tbb: To Be Budgeted amount in pence.
        allocations: Dictionary of category allocations in pence.

    Returns:
        BudgetSummary with all calculations.
    """
    total_allocated = Money(sum(allocations.values()))
    remaining_tbb = calculate_remaining_tbb(tbb, allocations)

    return BudgetSummary(
        tbb=tbb,
        total_allocated=total_allocated,
        remaining_tbb=remaining_tbb,
        allocations=allocations,
    )
