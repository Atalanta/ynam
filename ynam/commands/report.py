"""Report and inspect commands for viewing transaction data."""

import sqlite3
import sys
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from ynam.commands.review import categorize_transaction
from ynam.db import (
    get_all_budgets,
    get_category_breakdown,
    get_db_path,
    get_transactions_by_category,
)
from ynam.domain.models import CategoryName, Money
from ynam.domain.report import calculate_histogram_bar_length, create_full_report

console = Console()


def inspect_command(
    category: str,
    all: bool = False,
    month: str | None = None,
) -> None:
    """Inspect transactions for a specific category."""
    db_path = get_db_path()

    try:
        if all:
            since_date = None
            until_date = None
            period = "All Time"
        elif month:
            since_date = f"{month}-01"
            # Calculate first day of next month for upper bound
            month_dt = datetime.strptime(month, "%Y-%m")
            next_month_dt = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
            until_date = next_month_dt.strftime("%Y-%m-%d")
            period = month_dt.strftime("%B %Y")
        else:
            since_date = datetime.now().strftime("%Y-%m-01")
            # Calculate first day of next month for upper bound
            now = datetime.now()
            next_month_dt = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
            until_date = next_month_dt.strftime("%Y-%m-%d")
            period = now.strftime("%B %Y")

        transactions = get_transactions_by_category(category, db_path, since_date, until_date)

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

        total = 0
        for idx, txn in enumerate(transactions, 1):
            amount = txn["amount"]
            total += amount

            if amount < 0:
                amount_display = f"[red]-£{abs(amount) / 100:,.2f}[/red]"
            else:
                amount_display = f"[green]+£{amount / 100:,.2f}[/green]"

            table.add_row(str(idx), txn["date"], txn["description"], amount_display)

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
        if all:
            since_date = None
            until_date = None
            period = "All Time"
            report_month = None
        elif month:
            since_date = f"{month}-01"
            # Calculate first day of next month for upper bound
            month_dt = datetime.strptime(month, "%Y-%m")
            next_month_dt = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
            until_date = next_month_dt.strftime("%Y-%m-%d")
            period = month_dt.strftime("%B %Y")
            report_month = month
        else:
            since_date = datetime.now().strftime("%Y-%m-01")
            # Calculate first day of next month for upper bound
            now = datetime.now()
            next_month_dt = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
            until_date = next_month_dt.strftime("%Y-%m-%d")
            period = now.strftime("%B %Y")
            report_month = now.strftime("%Y-%m")

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
            if histogram:
                max_amount = Money(max(abs(cat.amount) for cat in report.expenses.categories))
                bar_width = 30

                for cat_report in report.expenses.categories:
                    actual = abs(cat_report.amount) / 100
                    budget_pence = cat_report.budget

                    if budget_pence:
                        budget = budget_pence / 100
                        percentage = cat_report.percentage or 0
                        budget_display = f"/ £{budget:,.2f} ({percentage:.0f}%)"

                        # Color based on budget status
                        if percentage > 100:
                            budget_display = f"[red]{budget_display}[/red]"
                        elif percentage > 90:
                            budget_display = f"[yellow]{budget_display}[/yellow]"
                        else:
                            budget_display = f"[green]{budget_display}[/green]"
                    else:
                        budget_display = ""

                    amount_display = f"£{actual:,.2f}"
                    bar_length = calculate_histogram_bar_length(cat_report.amount, max_amount, bar_width)
                    bar = "█" * bar_length
                    console.print(f"  {cat_report.category:20} {amount_display:>12} {budget_display:30} {bar}")
            else:
                for cat_report in report.expenses.categories:
                    actual = abs(cat_report.amount) / 100
                    budget_pence = cat_report.budget

                    if budget_pence:
                        budget = budget_pence / 100
                        percentage = cat_report.percentage or 0
                        console.print(f"  {cat_report.category}: £{actual:,.2f} / £{budget:,.2f} ({percentage:.0f}%)")
                    else:
                        console.print(f"  {cat_report.category}: £{actual:,.2f}")

            total_expenses = abs(report.expenses.total) / 100
            total_budget_pence = report.expenses.total_budget

            if total_budget_pence > 0:
                budget_display = f" / £{total_budget_pence / 100:,.2f}"
            else:
                budget_display = ""

            console.print(f"\n  [bold]Total expenses:[/bold] £{total_expenses:,.2f}{budget_display}\n")

        if report.income.categories:
            console.print("[bold green]Income by category:[/bold green]\n")
            if histogram:
                max_amount = Money(max(cat.amount for cat in report.income.categories))
                bar_width = 40

                for cat_report in report.income.categories:
                    amount_display = f"£{cat_report.amount / 100:,.2f}"
                    bar_length = calculate_histogram_bar_length(cat_report.amount, max_amount, bar_width)
                    bar = "█" * bar_length
                    console.print(f"  {cat_report.category:20} {amount_display:>12} {bar}")
            else:
                for cat_report in report.income.categories:
                    console.print(f"  {cat_report.category}: £{cat_report.amount / 100:,.2f}")

            total_income = report.income.total / 100
            console.print(f"\n  [bold]Total income:[/bold] £{total_income:,.2f}\n")

        if report.expenses.categories and report.income.categories:
            net = report.net / 100
            console.print(f"[bold cyan]Net:[/bold cyan] £{net:,.2f}")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
