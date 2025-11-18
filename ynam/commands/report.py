"""Report and inspect commands for viewing transaction data."""

import sqlite3
import sys
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from ynam.commands.review import categorize_transaction
from ynam.domain.models import CategoryName, Money, Month
from ynam.domain.report import (
    CategoryReport,
    calculate_histogram_bar_length,
    calculate_month_date_range,
    create_full_report,
    format_month_display,
)
from ynam.store.queries import (
    get_all_budgets,
    get_category_breakdown,
    get_transactions_by_category,
)
from ynam.store.schema import get_db_path

console = Console()


def compute_report_period(all: bool, month: Month | None) -> tuple[str | None, str | None, str, Month | None]:
    """Compute date range and period display for report.

    Args:
        all: Whether to report all time.
        month: Optional specific month (YYYY-MM format).

    Returns:
        Tuple of (since_date, until_date, period_display, report_month).
    """
    if all:
        return None, None, "All Time", None

    if month:
        # Parse month string to year and month integers
        month_dt = datetime.strptime(month, "%Y-%m")
        year = month_dt.year
        month_int = month_dt.month

        # Use pure function for date calculation
        since_date, until_date = calculate_month_date_range(year, month_int)
        period = format_month_display(year, month_int)

        return since_date, until_date, period, month

    # Current month - only impure part is getting current date
    now = datetime.now()
    year = now.year
    month_int = now.month

    # Use pure functions for calculations
    since_date, until_date = calculate_month_date_range(year, month_int)
    period = format_month_display(year, month_int)
    report_month = Month(now.strftime("%Y-%m"))

    return since_date, until_date, period, report_month


def format_budget_display_with_color(percentage: float) -> str:
    """Format budget display with color based on percentage.

    Args:
        percentage: Budget usage percentage.

    Returns:
        Colored string for budget display.
    """
    budget_text = f"({percentage:.0f}%)"
    if percentage > 100:
        return f"[red]{budget_text}[/red]"
    elif percentage > 90:
        return f"[yellow]{budget_text}[/yellow]"
    else:
        return f"[green]{budget_text}[/green]"


def render_expense_line(cat_report: CategoryReport, histogram: bool, max_amount: Money | None, bar_width: int) -> None:
    """Render single expense category line.

    Args:
        cat_report: CategoryReport with expense data.
        histogram: Whether to show histogram bars.
        max_amount: Maximum amount for histogram scaling.
        bar_width: Width of histogram bar in characters.
    """
    actual = abs(cat_report.amount) / 100
    budget_pence = cat_report.budget

    if budget_pence:
        budget = budget_pence / 100
        percentage = cat_report.percentage or 0
        budget_display = f"/ £{budget:,.2f} {format_budget_display_with_color(percentage)}"
    else:
        budget_display = ""

    amount_display = f"£{actual:,.2f}"

    if histogram and max_amount:
        bar_length = calculate_histogram_bar_length(cat_report.amount, max_amount, bar_width)
        bar = "█" * bar_length
        console.print(f"  {cat_report.category:20} {amount_display:>12} {budget_display:30} {bar}")
    else:
        if budget_pence:
            budget = budget_pence / 100
            percentage = cat_report.percentage or 0
            console.print(f"  {cat_report.category}: £{actual:,.2f} / £{budget:,.2f} ({percentage:.0f}%)")
        else:
            console.print(f"  {cat_report.category}: £{actual:,.2f}")


def render_income_line(cat_report: CategoryReport, histogram: bool, max_amount: Money | None, bar_width: int) -> None:
    """Render single income category line.

    Args:
        cat_report: CategoryReport with income data.
        histogram: Whether to show histogram bars.
        max_amount: Maximum amount for histogram scaling.
        bar_width: Width of histogram bar in characters.
    """
    amount_display = f"£{cat_report.amount / 100:,.2f}"

    if histogram and max_amount:
        bar_length = calculate_histogram_bar_length(cat_report.amount, max_amount, bar_width)
        bar = "█" * bar_length
        console.print(f"  {cat_report.category:20} {amount_display:>12} {bar}")
    else:
        console.print(f"  {cat_report.category}: £{cat_report.amount / 100:,.2f}")


def inspect_command(
    category: str,
    all: bool = False,
    month: str | None = None,
) -> None:
    """Inspect transactions for a specific category."""
    db_path = get_db_path()

    try:
        month_typed = Month(month) if month else None
        since_date, until_date, period, _ = compute_report_period(all, month_typed)

        transactions = get_transactions_by_category(CategoryName(category), db_path, since_date, until_date)

        if not transactions:
            console.print(f"[yellow]No transactions found for category '{category}'[/yellow]")
            return

        is_unreviewed = category.lower() == "unreviewed"

        title = f"{category} - {period} ({len(transactions)} transactions)"
        table = Table(title=title)

        # Always show # column for selection
        table.add_column("#", style="dim", justify="right")
        table.add_column("Date", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Amount", justify="right")
        table.add_column("Source", style="dim")

        total = 0
        for idx, txn in enumerate(transactions, 1):
            amount = txn["amount"]
            total += amount

            if amount < 0:
                amount_display = f"[red]-£{abs(amount) / 100:,.2f}[/red]"
            else:
                amount_display = f"[green]+£{amount / 100:,.2f}[/green]"

            source = txn.get("source") or "[dim]-[/dim]"

            table.add_row(str(idx), txn["date"], txn["description"], amount_display, source)

        console.print(table)

        if total < 0:
            total_display = f"[red]-£{abs(total) / 100:,.2f}[/red]"
        else:
            total_display = f"[green]+£{total / 100:,.2f}[/green]"

        console.print(f"\n[bold]Total:[/bold] {total_display}")

        # Prompt for selection
        if is_unreviewed:
            prompt_text = f"\nSelect transaction to categorize (1-{len(transactions)}, or q to quit)"
        else:
            prompt_text = f"\nSelect transaction to recategorize (1-{len(transactions)}, or q to quit)"

        choice = typer.prompt(prompt_text, type=str, default="q")
        if choice.lower() != "q":
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(transactions):
                    console.print()
                    categorize_transaction(transactions[idx], db_path)
                else:
                    console.print("[red]Invalid selection[/red]")
            except ValueError:
                console.print("[red]Invalid input[/red]")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


def report_command(
    sort_by: str = "value",
    histogram: bool = True,
    all: bool = False,
    month: str | None = None,
) -> None:
    """Generate income and spending breakdown report."""
    db_path = get_db_path()

    try:
        month_typed = Month(month) if month else None
        since_date, until_date, period, report_month = compute_report_period(all, month_typed)

        breakdown_raw = get_category_breakdown(db_path, since_date, until_date)

        if not breakdown_raw:
            console.print("[dim]No categorized transactions yet[/dim]")
            return

        # Get budgets for the report month (if not "all time")
        budgets_raw = get_all_budgets(report_month, db_path) if report_month else {}

        # Convert to domain types
        breakdown = {CategoryName(k): Money(v) for k, v in breakdown_raw.items()}
        budgets = {CategoryName(k): Money(v) for k, v in budgets_raw.items()}

        # Use functional core to create report
        report = create_full_report(breakdown, budgets, sort_by)

        # Imperative shell: Display results
        console.print(f"[bold cyan]{period}[/bold cyan]\n")

        if report.expenses.categories:
            console.print("[bold red]Expenses by category:[/bold red]\n")
            max_amount = Money(max(abs(cat.amount) for cat in report.expenses.categories)) if histogram else None
            bar_width = 30

            for cat_report in report.expenses.categories:
                render_expense_line(cat_report, histogram, max_amount, bar_width)

            total_expenses = abs(report.expenses.total) / 100
            total_budget_pence = report.expenses.total_budget

            if total_budget_pence > 0:
                budget_display = f" / £{total_budget_pence / 100:,.2f}"
            else:
                budget_display = ""

            console.print(f"\n  [bold]Total expenses:[/bold] £{total_expenses:,.2f}{budget_display}\n")

        if report.income.categories:
            console.print("[bold green]Income by category:[/bold green]\n")
            max_amount = Money(max(cat.amount for cat in report.income.categories)) if histogram else None
            bar_width = 40

            for cat_report in report.income.categories:
                render_income_line(cat_report, histogram, max_amount, bar_width)

            total_income = report.income.total / 100
            console.print(f"\n  [bold]Total income:[/bold] £{total_income:,.2f}\n")

        if report.expenses.categories and report.income.categories:
            net = report.net / 100
            console.print(f"[bold cyan]Net:[/bold cyan] £{net:,.2f}")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
