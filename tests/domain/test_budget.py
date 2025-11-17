"""Tests for ynam.domain.budget pure functions."""

from ynam.domain.budget import (
    calculate_add_to_budget,
    calculate_remove_from_budget,
    calculate_set_budget,
    calculate_transfer,
    compute_budget_status,
)
from ynam.domain.models import CategoryName, Money


class TestCalculateSetBudget:
    """Tests for calculate_set_budget."""

    def test_set_positive_amount_with_sufficient_tbb(self) -> None:
        """Should set budget when TBB is sufficient."""
        new_alloc, new_remaining, error = calculate_set_budget(
            target=Money(10000),  # £100
            current_allocation=Money(5000),  # £50
            remaining_tbb=Money(20000),  # £200
        )
        assert new_alloc == Money(10000)
        assert new_remaining == Money(15000)  # £200 - (£100 - £50)
        assert error is None

    def test_set_amount_requiring_more_tbb_than_available(self) -> None:
        """Should return error when insufficient TBB."""
        new_alloc, new_remaining, error = calculate_set_budget(
            target=Money(30000),  # £300
            current_allocation=Money(5000),  # £50
            remaining_tbb=Money(10000),  # £100
        )
        assert new_alloc == Money(5000)  # Unchanged
        assert new_remaining == Money(10000)  # Unchanged
        assert error is not None
        assert "Not enough TBB" in error

    def test_set_to_zero(self) -> None:
        """Should allow setting to zero (returns money to TBB)."""
        new_alloc, new_remaining, error = calculate_set_budget(
            target=Money(0),
            current_allocation=Money(5000),
            remaining_tbb=Money(10000),
        )
        assert new_alloc == Money(0)
        assert new_remaining == Money(15000)  # Got £50 back
        assert error is None

    def test_set_negative_amount(self) -> None:
        """Should reject negative amounts."""
        new_alloc, new_remaining, error = calculate_set_budget(
            target=Money(-1000),
            current_allocation=Money(5000),
            remaining_tbb=Money(10000),
        )
        assert new_alloc == Money(5000)  # Unchanged
        assert new_remaining == Money(10000)  # Unchanged
        assert error == "Amount must be positive"


class TestCalculateAddToBudget:
    """Tests for calculate_add_to_budget."""

    def test_add_with_sufficient_tbb(self) -> None:
        """Should add amount from TBB."""
        new_alloc, new_remaining, error = calculate_add_to_budget(
            amount=Money(5000),  # £50
            current_allocation=Money(10000),  # £100
            remaining_tbb=Money(20000),  # £200
        )
        assert new_alloc == Money(15000)  # £150
        assert new_remaining == Money(15000)  # £150
        assert error is None

    def test_add_more_than_available_tbb(self) -> None:
        """Should return error when insufficient TBB."""
        new_alloc, new_remaining, error = calculate_add_to_budget(
            amount=Money(30000),  # £300
            current_allocation=Money(10000),
            remaining_tbb=Money(10000),  # Only £100 available
        )
        assert new_alloc == Money(10000)  # Unchanged
        assert new_remaining == Money(10000)  # Unchanged
        assert error is not None
        assert "Not enough TBB" in error

    def test_add_zero(self) -> None:
        """Should reject zero amount."""
        new_alloc, new_remaining, error = calculate_add_to_budget(
            amount=Money(0),
            current_allocation=Money(10000),
            remaining_tbb=Money(20000),
        )
        assert new_alloc == Money(10000)  # Unchanged
        assert new_remaining == Money(20000)  # Unchanged
        assert error == "Amount must be positive"

    def test_add_negative_amount(self) -> None:
        """Should reject negative amounts."""
        new_alloc, new_remaining, error = calculate_add_to_budget(
            amount=Money(-5000),
            current_allocation=Money(10000),
            remaining_tbb=Money(20000),
        )
        assert new_alloc == Money(10000)  # Unchanged
        assert new_remaining == Money(20000)  # Unchanged
        assert error == "Amount must be positive"


class TestCalculateRemoveFromBudget:
    """Tests for calculate_remove_from_budget."""

    def test_remove_within_allocation(self) -> None:
        """Should remove amount and return to TBB."""
        new_alloc, new_remaining, error = calculate_remove_from_budget(
            amount=Money(5000),  # £50
            current_allocation=Money(10000),  # £100
            remaining_tbb=Money(20000),  # £200
        )
        assert new_alloc == Money(5000)  # £50
        assert new_remaining == Money(25000)  # £250
        assert error is None

    def test_remove_more_than_allocated(self) -> None:
        """Should return error when removing more than allocated."""
        new_alloc, new_remaining, error = calculate_remove_from_budget(
            amount=Money(15000),  # £150
            current_allocation=Money(10000),  # Only £100 allocated
            remaining_tbb=Money(20000),
        )
        assert new_alloc == Money(10000)  # Unchanged
        assert new_remaining == Money(20000)  # Unchanged
        assert error is not None
        assert "Can't remove more than allocated" in error

    def test_remove_zero(self) -> None:
        """Should reject zero amount."""
        new_alloc, new_remaining, error = calculate_remove_from_budget(
            amount=Money(0),
            current_allocation=Money(10000),
            remaining_tbb=Money(20000),
        )
        assert new_alloc == Money(10000)  # Unchanged
        assert new_remaining == Money(20000)  # Unchanged
        assert error == "Amount must be positive"


class TestCalculateTransfer:
    """Tests for calculate_transfer."""

    def test_transfer_within_allocation(self) -> None:
        """Should transfer between categories."""
        new_from, new_to, error = calculate_transfer(
            amount=Money(5000),  # £50
            from_allocation=Money(10000),  # £100
            to_allocation=Money(3000),  # £30
        )
        assert new_from == Money(5000)  # £50
        assert new_to == Money(8000)  # £80
        assert error is None

    def test_transfer_more_than_allocated(self) -> None:
        """Should return error when transferring more than allocated."""
        new_from, new_to, error = calculate_transfer(
            amount=Money(15000),  # £150
            from_allocation=Money(10000),  # Only £100
            to_allocation=Money(3000),
        )
        assert new_from == Money(10000)  # Unchanged
        assert new_to == Money(3000)  # Unchanged
        assert error is not None
        assert "Can't transfer more than allocated" in error

    def test_transfer_to_empty_category(self) -> None:
        """Should transfer to category with zero allocation."""
        new_from, new_to, error = calculate_transfer(
            amount=Money(5000),
            from_allocation=Money(10000),
            to_allocation=Money(0),  # Empty category
        )
        assert new_from == Money(5000)
        assert new_to == Money(5000)
        assert error is None

    def test_transfer_zero(self) -> None:
        """Should reject zero amount."""
        new_from, new_to, error = calculate_transfer(
            amount=Money(0),
            from_allocation=Money(10000),
            to_allocation=Money(3000),
        )
        assert new_from == Money(10000)  # Unchanged
        assert new_to == Money(3000)  # Unchanged
        assert error == "Amount must be positive"


class TestComputeBudgetStatus:
    """Tests for compute_budget_status."""

    def test_compute_with_multiple_categories(self) -> None:
        """Should compute status for multiple categories."""
        budgets = {
            CategoryName("Groceries"): Money(50000),  # £500
            CategoryName("Transport"): Money(20000),  # £200
        }
        spending = {
            CategoryName("Groceries"): Money(-30000),  # Spent £300
            CategoryName("Transport"): Money(-15000),  # Spent £150
        }
        status = compute_budget_status(
            tbb=Money(100000),  # £1000
            budgets=budgets,
            spending=spending,
        )

        assert status.tbb == Money(100000)
        assert status.total_allocated == Money(70000)  # £700
        assert status.remaining_tbb == Money(30000)  # £300
        assert len(status.categories) == 2

        # Categories should be sorted alphabetically
        assert status.categories[0].category == CategoryName("Groceries")
        assert status.categories[0].allocated == Money(50000)
        assert status.categories[0].spent == Money(30000)
        assert status.categories[0].available == Money(20000)  # £200 left

        assert status.categories[1].category == CategoryName("Transport")
        assert status.categories[1].allocated == Money(20000)
        assert status.categories[1].spent == Money(15000)
        assert status.categories[1].available == Money(5000)  # £50 left

    def test_compute_with_overspending(self) -> None:
        """Should handle overspending (negative available)."""
        budgets = {CategoryName("Eating Out"): Money(10000)}  # £100 budgeted
        spending = {CategoryName("Eating Out"): Money(-15000)}  # Spent £150

        status = compute_budget_status(
            tbb=Money(10000),
            budgets=budgets,
            spending=spending,
        )

        assert status.categories[0].available == Money(-5000)  # £50 overspent

    def test_compute_with_no_spending(self) -> None:
        """Should handle categories with no spending."""
        budgets = {CategoryName("Savings"): Money(50000)}
        spending: dict[CategoryName, Money] = {}  # No spending yet

        status = compute_budget_status(
            tbb=Money(50000),
            budgets=budgets,
            spending=spending,
        )

        assert status.categories[0].allocated == Money(50000)
        assert status.categories[0].spent == Money(0)
        assert status.categories[0].available == Money(50000)  # Full amount available

    def test_compute_with_over_allocation(self) -> None:
        """Should handle over-allocation (negative remaining TBB)."""
        budgets = {
            CategoryName("Category1"): Money(60000),
            CategoryName("Category2"): Money(50000),
        }
        status = compute_budget_status(
            tbb=Money(100000),  # Only £1000 TBB
            budgets=budgets,
            spending={},
        )

        assert status.remaining_tbb == Money(-10000)  # £100 over-allocated

    def test_compute_handles_positive_transactions_as_zero_spent(self) -> None:
        """Should treat positive transactions (income) as zero spending."""
        budgets = {CategoryName("Freelance"): Money(0)}
        spending = {CategoryName("Freelance"): Money(50000)}  # Positive = income

        status = compute_budget_status(
            tbb=Money(100000),
            budgets=budgets,
            spending=spending,
        )

        # Positive spending should not count as expenses
        assert status.categories[0].spent == Money(0)
        assert status.categories[0].available == Money(0)
