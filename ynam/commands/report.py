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

        breakdown = get_category_breakdown(db_path, since_date, until_date)

        if not breakdown:
            console.print("[dim]No categorized transactions yet[/dim]")
            return

        expenses = {cat: amt for cat, amt in breakdown.items() if amt < 0}
        income = {cat: amt for cat, amt in breakdown.items() if amt > 0}

        if sort_by == "alpha":
            sorted_expenses = sorted(expenses.items(), key=lambda x: x[0])
            sorted_income = sorted(income.items(), key=lambda x: x[0])
        else:
            sorted_expenses = sorted(expenses.items(), key=lambda x: x[1])
            sorted_income = sorted(income.items(), key=lambda x: x[1], reverse=True)

        # Get budgets for the report month (if not "all time")
        budgets = get_all_budgets(report_month, db_path) if report_month else {}

        console.print(f"[bold cyan]{period}[/bold cyan]\n")

        if expenses:
            console.print("[bold red]Expenses by category:[/bold red]\n")
            if histogram:
                max_amount = max(abs(amount) for _, amount in sorted_expenses)
                bar_width = 30

                for category, amount in sorted_expenses:
                    actual = abs(amount) / 100
                    budget_pence = budgets.get(category)

                    if budget_pence:
                        budget = budget_pence / 100
                        percentage = (actual / budget * 100) if budget > 0 else 0
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
                    bar_length = int((abs(amount) / max_amount) * bar_width) if max_amount > 0 else 0
                    bar = "█" * bar_length
                    console.print(f"  {category:20} {amount_display:>12} {budget_display:30} {bar}")
            else:
                for category, amount in sorted_expenses:
                    actual = abs(amount) / 100
                    budget_pence = budgets.get(category)

                    if budget_pence:
                        budget = budget_pence / 100
                        percentage = (actual / budget * 100) if budget > 0 else 0
                        console.print(f"  {category}: £{actual:,.2f} / £{budget:,.2f} ({percentage:.0f}%)")
                    else:
                        console.print(f"  {category}: £{actual:,.2f}")

            total_expenses = sum(expenses.values())
            total_budget = sum(budgets.get(cat, 0) for cat in expenses.keys())

            if total_budget > 0:
                budget_display = f" / £{total_budget / 100:,.2f}"
            else:
                budget_display = ""

            console.print(f"\n  [bold]Total expenses:[/bold] £{abs(total_expenses) / 100:,.2f}{budget_display}\n")

        if income:
            console.print("[bold green]Income by category:[/bold green]\n")
            if histogram:
                max_amount = max(amount for _, amount in sorted_income)
                bar_width = 40

                for category, amount in sorted_income:
                    amount_display = f"£{amount / 100:,.2f}"
                    bar_length = int((amount / max_amount) * bar_width) if max_amount > 0 else 0
                    bar = "█" * bar_length
                    console.print(f"  {category:20} {amount_display:>12} {bar}")
            else:
                for category, amount in sorted_income:
                    console.print(f"  {category}: £{amount / 100:,.2f}")

            total_income = sum(income.values())
            console.print(f"\n  [bold]Total income:[/bold] £{total_income / 100:,.2f}\n")

        if expenses and income:
            net = sum(breakdown.values())
            console.print(f"[bold cyan]Net:[/bold cyan] £{net / 100:,.2f}")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
