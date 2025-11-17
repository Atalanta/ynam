"""Budget command for managing category budgets."""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ynam.db import (
    get_all_budgets,
    get_all_categories,
    get_category_breakdown,
    get_db_path,
    get_monthly_tbb,
    set_budget,
    set_monthly_tbb,
)
from ynam.domain.budget import (
    calculate_add_to_budget,
    calculate_remove_from_budget,
    calculate_rollover_summary,
    calculate_set_budget,
)
from ynam.domain.models import CategoryName, Money, Month

console = Console()


def handle_set_budget_action(
    category: CategoryName,
    current_allocation: Money,
    remaining_tbb: Money,
    target_month: Month,
    db_path: Path,
) -> tuple[Money, Money]:
    """Handle '=' action: set budget to specific amount.

    Returns:
        Tuple of (new_allocation, new_remaining_tbb).
    """
    # Display context
    console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")
    console.print(f"[dim]Available TBB: £{remaining_tbb / 100:,.2f}[/dim]")

    # Get user input
    amount_str = typer.prompt("Set budget to (£)", type=str)

    try:
        target_pounds = float(amount_str)
        target_pence = Money(int(target_pounds * 100))

        # Call pure function for calculation
        new_allocation, new_remaining, error = calculate_set_budget(target_pence, current_allocation, remaining_tbb)

        if error:
            console.print(f"[red]{error}[/red]\n")
            return current_allocation, remaining_tbb

        # Persist to database
        set_budget(category, target_month, new_allocation, db_path)

        # Display result
        console.print(f"[green]✓ {category} now allocated: £{new_allocation / 100:,.2f}[/green]")
        difference = new_allocation - current_allocation
        if difference > 0:
            console.print(f"[dim]Took £{difference / 100:,.2f} from TBB[/dim]\n")
        elif difference < 0:
            console.print(f"[dim]Returned £{abs(difference) / 100:,.2f} to TBB[/dim]\n")
        else:
            console.print("[dim]No change[/dim]\n")

        return new_allocation, new_remaining

    except ValueError:
        console.print("[red]Invalid amount[/red]\n")
        return current_allocation, remaining_tbb


def handle_add_budget_action(
    category: CategoryName,
    current_allocation: Money,
    remaining_tbb: Money,
    target_month: Month,
    db_path: Path,
) -> tuple[Money, Money]:
    """Handle '+' action: add money from TBB.

    Returns:
        Tuple of (new_allocation, new_remaining_tbb).
    """
    # Early check for available TBB
    if remaining_tbb <= 0:
        console.print("[red]No TBB remaining to add[/red]\n")
        return current_allocation, remaining_tbb

    # Display context
    console.print(f"[dim]Available TBB: £{remaining_tbb / 100:,.2f}[/dim]")

    # Get user input
    amount_str = typer.prompt("Amount to add (£)", type=str)

    try:
        amount_pounds = float(amount_str)
        amount_pence = Money(int(amount_pounds * 100))

        # Call pure function for calculation
        new_allocation, new_remaining, error = calculate_add_to_budget(amount_pence, current_allocation, remaining_tbb)

        if error:
            console.print(f"[red]{error}[/red]\n")
            return current_allocation, remaining_tbb

        # Persist to database
        set_budget(category, target_month, new_allocation, db_path)

        # Display result
        console.print(f"[green]✓ {category} now allocated: £{new_allocation / 100:,.2f}[/green]\n")

        return new_allocation, new_remaining

    except ValueError:
        console.print("[red]Invalid amount[/red]\n")
        return current_allocation, remaining_tbb


def handle_remove_budget_action(
    category: CategoryName,
    current_allocation: Money,
    remaining_tbb: Money,
    target_month: Month,
    db_path: Path,
) -> tuple[Money, Money]:
    """Handle '-' action: remove money (returns to TBB).

    Returns:
        Tuple of (new_allocation, new_remaining_tbb).
    """
    # Early check for available allocation
    if current_allocation <= 0:
        console.print("[red]No allocation to remove[/red]\n")
        return current_allocation, remaining_tbb

    # Display context
    console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")

    # Get user input
    amount_str = typer.prompt("Amount to remove (£)", type=str)

    try:
        amount_pounds = float(amount_str)
        amount_pence = Money(int(amount_pounds * 100))

        # Call pure function for calculation
        new_allocation, new_remaining, error = calculate_remove_from_budget(
            amount_pence, current_allocation, remaining_tbb
        )

        if error:
            console.print(f"[red]{error}[/red]\n")
            return current_allocation, remaining_tbb

        # Persist to database
        set_budget(category, target_month, new_allocation, db_path)

        # Display result
        console.print(f"[green]✓ {category} now allocated: £{new_allocation / 100:,.2f}[/green]")
        console.print(f"[dim]Returned £{amount_pence / 100:,.2f} to TBB[/dim]\n")

        return new_allocation, new_remaining

    except ValueError:
        console.print("[red]Invalid amount[/red]\n")
        return current_allocation, remaining_tbb


def handle_transfer_budget_action(
    category: CategoryName,
    current_allocation: Money,
    categories: list[CategoryName],
    budgets: dict[CategoryName, Money],
    target_month: Month,
    db_path: Path,
) -> dict[CategoryName, Money]:
    """Handle 't' action: transfer to another category.

    Returns:
        Updated budgets dictionary.
    """
    console.print("\nTransfer to:")
    other_categories = [cat for cat in categories if cat != category]
    for idx2, cat in enumerate(other_categories, 1):
        console.print(f"  {idx2}. {cat}")

    target_choice = typer.prompt(f"\nSelect target category (1-{len(other_categories)})", type=str)

    try:
        target_idx = int(target_choice) - 1
        if target_idx < 0 or target_idx >= len(other_categories):
            console.print("[red]Invalid selection[/red]\n")
            return budgets

        target_category = other_categories[target_idx]

        console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")
        amount_str = typer.prompt("Amount to transfer (£)", type=str)

        amount_pounds = float(amount_str)
        amount_pence = int(amount_pounds * 100)

        if amount_pence <= 0:
            console.print("[red]Amount must be positive[/red]\n")
            return budgets

        if amount_pence > current_allocation:
            console.print(f"[red]Can't transfer more than allocated (only £{current_allocation / 100:,.2f})[/red]\n")
            return budgets

        # Update source category
        new_source = current_allocation - amount_pence
        set_budget(category, target_month, new_source, db_path)
        budgets[category] = Money(new_source)

        # Update target category
        target_current = budgets.get(target_category, Money(0))
        new_target = target_current + amount_pence
        set_budget(target_category, target_month, new_target, db_path)
        budgets[target_category] = Money(new_target)

        console.print(f"[green]✓ Transferred £{amount_pence / 100:,.2f} from {category} to {target_category}[/green]")
        console.print(f"  {category}: £{new_source / 100:,.2f}")
        console.print(f"  {target_category}: £{new_target / 100:,.2f}\n")

        return budgets

    except (ValueError, IndexError):
        console.print("[red]Invalid input[/red]\n")
        return budgets


def show_budget_status(target_month: str, month_display: str, db_path: Path) -> None:
    """Show budget status for a specific month.

    Args:
        target_month: Month in YYYY-MM format.
        month_display: Month display string (e.g., "November 2025").
        db_path: Path to database.
    """
    console.print(f"[bold cyan]{month_display} Budget Status[/bold cyan]\n")

    # Get TBB
    tbb_pence = get_monthly_tbb(target_month, db_path)
    if tbb_pence is None:
        console.print(f"[yellow]No budget set for {month_display}[/yellow]")
        console.print("[dim]Use 'ynam budget --set-tbb <amount>' to set TBB first[/dim]")
        return

    # Get budgets
    budgets = get_all_budgets(target_month, db_path)
    total_allocated = sum(budgets.values())
    remaining_tbb = tbb_pence - total_allocated

    # Summary
    console.print(f"[bold]To Be Budgeted:[/bold]  £{tbb_pence / 100:,.2f}")
    console.print(f"[bold]Total Allocated:[/bold] £{total_allocated / 100:,.2f}")

    if remaining_tbb > 0:
        console.print(f"[bold]Remaining TBB:[/bold]    [yellow]£{remaining_tbb / 100:,.2f} (needs allocation)[/yellow]")
    elif remaining_tbb < 0:
        console.print(
            f"[bold]Over-allocated:[/bold]  [red]£{abs(remaining_tbb) / 100:,.2f} (allocated more than you have!)[/red]"
        )
    else:
        console.print("[bold]Remaining TBB:[/bold]    [green]£0.00 (fully allocated)[/green]")

    # Get actual spending for the month to show available
    target_date = datetime.strptime(target_month, "%Y-%m")
    since_date = target_date.strftime("%Y-%m-01")
    next_month_dt = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    until_date = next_month_dt.strftime("%Y-%m-%d")
    spending = get_category_breakdown(db_path, since_date, until_date)

    if not budgets:
        console.print("\n[dim]No categories allocated yet[/dim]")
        return

    console.print("\n[bold]Category Allocations:[/bold]\n")

    # Build table
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Category", style="white")
    table.add_column("Allocated", justify="right")
    table.add_column("Available", justify="right")

    for idx, category in enumerate(sorted(budgets.keys()), 1):
        allocated = budgets[category]
        spent_pence = spending.get(category, 0)
        spent_abs = abs(spent_pence) if spent_pence < 0 else 0
        available = allocated - spent_abs

        allocated_display = f"£{allocated / 100:,.2f}"

        if available < 0:
            available_display = f"[red]-£{abs(available) / 100:,.2f}[/red]"
        elif available == allocated:
            available_display = f"[dim]£{available / 100:,.2f}[/dim]"
        else:
            available_display = f"[green]£{available / 100:,.2f}[/green]"

        table.add_row(str(idx), category, allocated_display, available_display)

    console.print(table)
    console.print("\n[dim]Tip: Use 'ynam report' to see detailed spending analysis[/dim]")


def cli_adjust_budget(
    target_month: str, month_display: str, from_cat: str, to_cat: str, amount: float, db_path: Path
) -> None:
    """Adjust budget allocations via CLI arguments.

    Args:
        target_month: Month in YYYY-MM format.
        month_display: Month display string.
        from_cat: Source category (name, index, or "TBB").
        to_cat: Target category (name, index, or "TBB").
        amount: Amount to transfer in pounds.
        db_path: Path to database.
    """
    if amount <= 0:
        console.print("[red]Amount must be positive[/red]")
        sys.exit(1)

    amount_pence = int(amount * 100)

    # Get TBB and budgets
    tbb_pence = get_monthly_tbb(target_month, db_path)
    if tbb_pence is None:
        console.print(f"[yellow]No budget set for {month_display}[/yellow]")
        sys.exit(1)

    budgets = get_all_budgets(target_month, db_path)
    categories = sorted(budgets.keys())

    # Resolve from_cat
    if from_cat.upper() == "TBB":
        from_category = None
        from_display = "TBB"
    elif from_cat.isdigit():
        idx = int(from_cat) - 1
        if idx < 0 or idx >= len(categories):
            console.print(f"[red]Invalid index: {from_cat}[/red]")
            sys.exit(1)
        from_category = categories[idx]
        from_display = from_category
    else:
        if from_cat not in budgets:
            console.print(f"[red]Category not found: {from_cat}[/red]")
            sys.exit(1)
        from_category = from_cat
        from_display = from_category

    # Resolve to_cat
    if to_cat.upper() == "TBB":
        to_category = None
        to_display = "TBB"
    elif to_cat.isdigit():
        idx = int(to_cat) - 1
        if idx < 0 or idx >= len(categories):
            console.print(f"[red]Invalid index: {to_cat}[/red]")
            sys.exit(1)
        to_category = categories[idx]
        to_display = to_category
    else:
        # Allow creating new category if transferring from TBB
        if to_cat not in budgets and from_category is not None:
            console.print(f"[red]Category not found: {to_cat}[/red]")
            sys.exit(1)
        to_category = to_cat
        to_display = to_category

    # Validate transfer
    if from_category is None and to_category is None:
        console.print("[red]Cannot transfer from TBB to TBB[/red]")
        sys.exit(1)

    # Calculate current state
    total_allocated = sum(budgets.values())
    remaining_tbb = tbb_pence - total_allocated

    # From TBB to category
    if from_category is None:
        assert to_category is not None, "to_category must be set when from_category is None"
        if amount_pence > remaining_tbb:
            console.print(f"[red]Not enough TBB. Available: £{remaining_tbb / 100:,.2f}[/red]")
            sys.exit(1)

        current = budgets.get(to_category, 0)
        new_amount = current + amount_pence
        set_budget(to_category, target_month, new_amount, db_path)
        console.print(f"[green]✓ Allocated £{amount:.2f} from TBB to {to_display}[/green]")
        console.print(f"  {to_display}: £{new_amount / 100:,.2f}")
        console.print(f"  Remaining TBB: £{(remaining_tbb - amount_pence) / 100:,.2f}")

    # From category to TBB
    elif to_category is None:
        assert from_category is not None, "from_category must be set when to_category is None"
        current = budgets.get(from_category, 0)
        if amount_pence > current:
            console.print(f"[red]Not enough allocated in {from_display}. Allocated: £{current / 100:,.2f}[/red]")
            sys.exit(1)

        new_amount = current - amount_pence
        set_budget(from_category, target_month, new_amount, db_path)
        console.print(f"[green]✓ Returned £{amount:.2f} from {from_display} to TBB[/green]")
        console.print(f"  {from_display}: £{new_amount / 100:,.2f}")
        console.print(f"  Remaining TBB: £{(remaining_tbb + amount_pence) / 100:,.2f}")

    # From category to category
    else:
        from_current = budgets.get(from_category, 0)
        if amount_pence > from_current:
            console.print(f"[red]Not enough allocated in {from_display}. Allocated: £{from_current / 100:,.2f}[/red]")
            sys.exit(1)

        to_current = budgets.get(to_category, 0)

        from_new = from_current - amount_pence
        to_new = to_current + amount_pence

        set_budget(from_category, target_month, from_new, db_path)
        set_budget(to_category, target_month, to_new, db_path)

        console.print(f"[green]✓ Transferred £{amount:.2f} from {from_display} to {to_display}[/green]")
        console.print(f"  {from_display}: £{from_new / 100:,.2f}")
        console.print(f"  {to_display}: £{to_new / 100:,.2f}")


def copy_budget_with_rollover(source_month: str, target_month: str, month_display: str, db_path: Path) -> None:
    """Copy budget from source month to target month with unspent rollover.

    Args:
        source_month: Source month in YYYY-MM format.
        target_month: Target month in YYYY-MM format.
        month_display: Target month display string (e.g., "December 2025").
        db_path: Path to database.
    """
    try:
        source_month_display = datetime.strptime(source_month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        console.print(f"[red]Invalid source month format: {source_month}. Use YYYY-MM[/red]")
        sys.exit(1)

    # Get source month budgets
    source_budgets = get_all_budgets(source_month, db_path)
    if not source_budgets:
        console.print(f"[yellow]No budget found for {source_month_display}[/yellow]")
        sys.exit(1)

    # Get source month TBB
    source_tbb = get_monthly_tbb(source_month, db_path)
    if source_tbb is None:
        console.print(f"[yellow]No TBB set for {source_month_display}[/yellow]")
        sys.exit(1)

    console.print(f"[cyan]Copying budget from {source_month_display} to {month_display}...[/cyan]\n")

    # Calculate source month spending
    source_date = datetime.strptime(source_month, "%Y-%m")
    since_date = source_date.strftime("%Y-%m-01")
    next_month_dt = (source_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    until_date = next_month_dt.strftime("%Y-%m-%d")
    source_spending_raw = get_category_breakdown(db_path, since_date, until_date)

    # Convert to domain types
    source_budgets_typed = {CategoryName(k): Money(v) for k, v in source_budgets.items()}
    source_spending_typed = {CategoryName(k): Money(v) for k, v in source_spending_raw.items()}

    # Use functional core to calculate rollover
    rollover_summary = calculate_rollover_summary(
        Money(source_tbb),
        source_budgets_typed,
        source_spending_typed,
    )

    # Imperative shell: Write to database
    for category, allocated in source_budgets.items():
        set_budget(category, target_month, allocated, db_path)

    console.print(f"[green]✓ Copied {len(source_budgets)} category budgets[/green]")

    set_monthly_tbb(target_month, rollover_summary.new_tbb, db_path)

    # Imperative shell: Display results
    console.print(f"\n[bold]Budget Summary for {month_display}:[/bold]")
    console.print(f"  Base TBB from {source_month_display}: £{rollover_summary.base_tbb / 100:,.2f}")

    if rollover_summary.rollovers:
        console.print("\n[bold cyan]Rolled over unspent amounts:[/bold cyan]")
        for rollover in rollover_summary.rollovers:
            console.print(f"  {rollover.category}: £{rollover.available / 100:,.2f}")

    console.print(f"\n[bold]Total TBB for {month_display}: £{rollover_summary.new_tbb / 100:,.2f}[/bold]")
    console.print(f"[dim]All category budgets copied from {source_month_display}[/dim]")


def adjust_budget_allocations(target_month: str, month_display: str, db_path: Path) -> None:
    """Interactively adjust budget allocations.

    Args:
        target_month: Month in YYYY-MM format.
        month_display: Month display string (e.g., "November 2025").
        db_path: Path to database.
    """
    # Get TBB
    tbb_pence = get_monthly_tbb(target_month, db_path)
    if tbb_pence is None:
        console.print(f"[yellow]No budget set for {month_display}[/yellow]")
        console.print("[dim]Use 'ynam budget --set-tbb <amount>' to set TBB first[/dim]")
        return

    # Get current budgets
    budgets = get_all_budgets(target_month, db_path)
    if not budgets:
        console.print(f"[yellow]No categories allocated for {month_display}[/yellow]")
        console.print("[dim]Use 'ynam budget' to allocate categories first[/dim]")
        return

    console.print(f"[bold cyan]{month_display} - Adjust Budget Allocations[/bold cyan]\n")

    while True:
        # Calculate remaining TBB
        total_allocated = sum(budgets.values())
        remaining_tbb = tbb_pence - total_allocated

        console.print(f"[bold]Remaining TBB:[/bold] £{remaining_tbb / 100:,.2f}\n")

        # Show numbered categories
        categories = sorted(budgets.keys())
        for idx, category in enumerate(categories, 1):
            allocated = budgets[category]
            console.print(f"  {idx}. {category:20} £{allocated / 100:,.2f}")

        console.print()
        choice = typer.prompt(f"Select category (1-{len(categories)}, or q to quit)", type=str)

        if choice.lower() == "q":
            console.print("[green]Done adjusting budget[/green]")
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(categories):
                console.print("[red]Invalid selection[/red]\n")
                continue

            category_str = categories[idx]
            category_name = CategoryName(category_str)
            current_allocation = Money(budgets[category_str])

            console.print(
                f"\n[bold]{category_name}[/bold] - Currently allocated: [cyan]£{current_allocation / 100:,.2f}[/cyan]"
            )
            console.print("\nOptions:")
            console.print("  + Add money from TBB")
            console.print("  - Remove money (returns to TBB)")
            console.print("  = Set to specific amount")
            console.print("  t Transfer to another category")
            console.print("  q Back to category list")

            action = typer.prompt("\nChoice", type=str)

            if action.lower() == "q":
                console.print()
                continue

            elif action == "=":
                new_alloc, new_remaining = handle_set_budget_action(
                    category_name, current_allocation, Money(remaining_tbb), Month(target_month), db_path
                )
                budgets[category_str] = new_alloc

            elif action == "+":
                new_alloc, new_remaining = handle_add_budget_action(
                    category_name, current_allocation, Money(remaining_tbb), Month(target_month), db_path
                )
                budgets[category_str] = new_alloc

            elif action == "-":
                new_alloc, new_remaining = handle_remove_budget_action(
                    category_name, current_allocation, Money(remaining_tbb), Month(target_month), db_path
                )
                budgets[category_str] = new_alloc

            elif action.lower() == "t":
                # Convert to domain types for transfer function
                categories_typed = [CategoryName(c) for c in categories]
                budgets_typed = {CategoryName(k): Money(v) for k, v in budgets.items()}
                budgets_typed = handle_transfer_budget_action(
                    category_name, current_allocation, categories_typed, budgets_typed, Month(target_month), db_path
                )
                # Convert back to primitive types for storage
                budgets = {str(k): int(v) for k, v in budgets_typed.items()}

            else:
                console.print("[red]Invalid option[/red]\n")

        except ValueError:
            console.print("[red]Invalid selection[/red]\n")


def allocate_budgets_interactively(target_month: str, month_display: str, db_path: Path) -> None:
    """Interactive budget allocation flow.

    Args:
        target_month: Month in YYYY-MM format.
        month_display: Month display string.
        db_path: Path to database.
    """
    categories = get_all_categories(db_path)

    if not categories:
        console.print("[yellow]No categories found. Create some categories first by reviewing transactions.[/yellow]")
        return

    # Get TBB for the month
    tbb_pence_or_none = get_monthly_tbb(target_month, db_path)
    if tbb_pence_or_none is None:
        console.print(f"[yellow]No TBB set for {month_display}. Use --set-tbb to set it first.[/yellow]")
        return

    # After None check, assign to non-nullable variable
    tbb_pence: int = tbb_pence_or_none

    console.print(f"[bold cyan]Budget allocation for {month_display}[/bold cyan]")
    console.print(f"[bold]To Be Budgeted:[/bold] £{tbb_pence / 100:,.2f}\n")

    # Calculate previous month date range for context
    target_date = datetime.strptime(target_month, "%Y-%m")
    prev_month_date = target_date.replace(day=1) - timedelta(days=1)
    prev_month_name = prev_month_date.strftime("%B %Y")

    # Get previous month's spending
    since_date = prev_month_date.replace(day=1).strftime("%Y-%m-%d")
    until_date = target_date.strftime("%Y-%m-%d")
    prev_month_breakdown = get_category_breakdown(db_path, since_date, until_date)

    # Get current budgets for this month
    current_budgets = get_all_budgets(target_month, db_path)
    total_allocated = sum(current_budgets.values())
    remaining = tbb_pence - total_allocated

    for category in categories:
        # Get current budget if exists
        current_budget = current_budgets.get(category)
        current_budget_display = f"£{current_budget / 100:.2f}" if current_budget else "not set"

        # Get previous month's spending
        prev_month_amount = prev_month_breakdown.get(category, 0)
        prev_month_display = f"£{abs(prev_month_amount) / 100:.2f}" if prev_month_amount < 0 else "£0.00"

        console.print(f"[bold]{category}[/bold]")
        console.print(f"  Current budget: [cyan]{current_budget_display}[/cyan]")
        console.print(f"  {prev_month_name} spending: [yellow]{prev_month_display}[/yellow]")
        console.print(f"  [dim]Remaining TBB: £{remaining / 100:,.2f}[/dim]")

        budget_input = typer.prompt("  Enter budget (in £, or 's' to skip)", type=str, default="s")

        if budget_input.lower() == "s":
            console.print("[dim]  Skipped[/dim]\n")
            continue

        try:
            budget_pounds = float(budget_input)
            budget_pence = int(budget_pounds * 100)

            if budget_pence < 0:
                console.print("[red]  Budget must be positive[/red]\n")
                continue

            # Update remaining calculation
            if current_budget:
                remaining += current_budget
            remaining -= budget_pence

            set_budget(category, target_month, budget_pence, db_path)
            console.print(f"[green]  ✓ Budget set to £{budget_pence / 100:.2f}[/green]")
            console.print(f"  [dim]Remaining TBB: £{remaining / 100:,.2f}[/dim]\n")

        except ValueError:
            console.print("[red]  Invalid amount[/red]\n")
            continue

    console.print("[green]Budget allocation complete![/green]", style="bold")
    console.print(f"[bold]Final remaining TBB:[/bold] £{remaining / 100:,.2f}")


def budget_command(
    set_tbb: float | None = None,
    status: bool = False,
    adjust: bool = False,
    copy_from: str | None = None,
    from_cat: str | None = None,
    to_cat: str | None = None,
    amount: float | None = None,
    month: str | None = None,
) -> None:
    """Set budget amounts for categories."""
    db_path = get_db_path()

    try:
        # Determine target month
        if month:
            target_month = month
            month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        else:
            target_month = datetime.now().strftime("%Y-%m")
            month_display = datetime.now().strftime("%B %Y")

        # Handle CLI adjust (--from --to --amount)
        if from_cat is not None or to_cat is not None or amount is not None:
            if not all([from_cat, to_cat, amount]):
                console.print("[red]--from, --to, and --amount must all be specified together[/red]")
                sys.exit(1)
            assert from_cat is not None and to_cat is not None and amount is not None
            cli_adjust_budget(target_month, month_display, from_cat, to_cat, amount, db_path)
            return

        # Handle --status flag
        if status:
            show_budget_status(target_month, month_display, db_path)
            return

        # Handle --adjust flag (interactive)
        if adjust:
            adjust_budget_allocations(target_month, month_display, db_path)
            return

        # Handle --copy-from flag
        if copy_from:
            copy_budget_with_rollover(copy_from, target_month, month_display, db_path)
            return

        # Handle --set-tbb flag
        if set_tbb is not None:
            if set_tbb < 0:
                console.print("[red]TBB amount must be positive[/red]")
                sys.exit(1)

            tbb_pence = int(set_tbb * 100)
            set_monthly_tbb(target_month, tbb_pence, db_path)
            console.print(f"[green]✓ Set To Be Budgeted for {month_display}: £{tbb_pence / 100:,.2f}[/green]")
            return

        # Budget allocation flow
        allocate_budgets_interactively(target_month, month_display, db_path)

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
