"""CLI entry point for ynam."""

import sqlite3
import sys
from datetime import datetime, timedelta

import requests
import typer
from rich.columns import Columns
from rich.console import Console

from ynam.db import (
    add_category,
    get_all_categories,
    get_auto_allocate_rule,
    get_category_breakdown,
    get_db_path,
    get_most_recent_transaction_date,
    get_suggested_category,
    get_unreviewed_transactions,
    init_database,
    insert_transaction,
    set_auto_allocate_rule,
    update_transaction_review,
)
from ynam.starling import get_account_info, get_token, get_transactions

app = typer.Typer(
    name="ynam",
    help="You Need A Mirror - A YNAB-inspired money management tool",
    add_completion=False,
)
console = Console()


@app.callback()
def main() -> None:
    """You Need A Mirror - A YNAB-inspired money management tool."""
    pass


@app.command()
def initdb() -> None:
    """Initialize the ynam database."""
    db_path = get_db_path()

    try:
        console.print(f"[cyan]Initializing database at {db_path}...[/cyan]")
        init_database(db_path)
        console.print("[green]Database initialized successfully![/green]", style="bold")
        console.print(f"[dim]Location: {db_path}[/dim]")

    except sqlite3.Error as e:
        console.print(f"[red]Error initializing database: {e}[/red]", style="bold")
        sys.exit(1)
    except OSError as e:
        console.print(
            f"[red]Filesystem error: {e}[/red]",
            style="bold",
        )
        sys.exit(1)


@app.command()
def fetch(days: int = typer.Option(30, help="Number of days to fetch if no transactions exist")) -> None:
    """Fetch transactions from Starling Bank API."""
    token = get_token()
    if not token:
        console.print("[red]STARLING_TOKEN environment variable not set[/red]", style="bold")
        sys.exit(1)

    db_path = get_db_path()

    try:
        console.print("[cyan]Fetching account information...[/cyan]")
        account_uid, category_uid = get_account_info(token)

        most_recent_date = get_most_recent_transaction_date(db_path)
        if most_recent_date:
            since_date = datetime.fromisoformat(most_recent_date)
            console.print(f"[cyan]Fetching transactions since {most_recent_date}...[/cyan]")
        else:
            since_date = datetime.now() - timedelta(days=days)
            console.print(f"[cyan]Fetching transactions from last {days} days...[/cyan]")

        console.print("[cyan]Fetching transactions...[/cyan]")
        transactions = get_transactions(token, account_uid, category_uid, since_date)

        console.print(f"[cyan]Inserting {len(transactions)} transactions...[/cyan]")
        for txn in transactions:
            date = txn["transactionTime"][:10]
            description = txn.get("counterPartyName", "Unknown")
            amount = int(txn["amount"]["minorUnits"])

            if txn.get("direction") == "OUT":
                amount = -amount

            insert_transaction(date, description, amount, db_path)

        console.print(f"[green]Successfully fetched {len(transactions)} transactions![/green]", style="bold")

    except requests.RequestException as e:
        console.print(f"[red]API error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


@app.command()
def review() -> None:
    """Review and categorize unreviewed transactions."""
    db_path = get_db_path()
    session_skip_rules = {}

    try:
        transactions = get_unreviewed_transactions(db_path)

        if not transactions:
            console.print("[yellow]No unreviewed transactions found[/yellow]")
            return

        console.print(f"[cyan]Found {len(transactions)} unreviewed transactions[/cyan]\n")

        for txn in transactions:
            amount = txn['amount']
            if amount < 0:
                amount_display = f"-£{abs(amount) / 100:.2f}"
            else:
                amount_display = f"+£{amount / 100:.2f}"

            console.print(f"[bold]Date:[/bold] {txn['date']}")
            console.print(f"[bold]Description:[/bold] {txn['description']}")
            console.print(f"[bold]Amount:[/bold] {amount_display}\n")

            if txn["description"] in session_skip_rules:
                console.print("[dim]Skipping (session rule)[/dim]\n")
                continue

            auto_category = get_auto_allocate_rule(txn["description"], db_path)
            if auto_category:
                update_transaction_review(txn["id"], auto_category, db_path)
                console.print(f"[green]Auto-allocating as: {auto_category}[/green]\n")
                continue

            categories = get_all_categories(db_path)
            suggested = get_suggested_category(txn["description"], db_path)

            if categories:
                console.print("[cyan]Categories:[/cyan]")
                category_items = [f"{idx}. {cat}" for idx, cat in enumerate(categories, 1)]
                console.print(Columns(category_items, equal=True, expand=False, column_first=True))
                console.print("  n. New category")

                if suggested:
                    console.print(f"\n[yellow]Suggested:[/yellow] [bold]{suggested}[/bold] [dim](press Enter to accept, a to auto-allocate all)[/dim]")
                    prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, a to auto-allocate, q to quit)"
                    choice = typer.prompt(prompt_text, type=str, default="")
                else:
                    prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, q to quit)"
                    choice = typer.prompt(prompt_text, type=str)
            else:
                console.print("[dim]No categories yet[/dim]")
                choice = typer.prompt("\nEnter category name (or s to skip, q to quit)", type=str)

            if choice.lower() == "q":
                console.print("[yellow]Exiting review[/yellow]")
                return

            if choice.lower() == "s":
                skip_all = typer.confirm("Skip all future transactions like this in this session?", default=False)
                if skip_all:
                    session_skip_rules[txn["description"]] = True
                    console.print("[dim]Skipped (will skip similar transactions this session)[/dim]\n")
                else:
                    console.print("[dim]Skipped[/dim]\n")
                continue

            if choice.lower() == "a" and suggested:
                set_auto_allocate_rule(txn["description"], suggested, db_path)
                update_transaction_review(txn["id"], suggested, db_path)
                console.print(f"[green]Auto-allocating as: {suggested}[/green]\n")
                continue

            if not categories:
                add_category(choice, db_path)
                selected_category = choice
                console.print(f"[green]Added new category: {choice}[/green]")
            elif choice == "" and suggested:
                selected_category = suggested
            elif choice.lower() == "n":
                new_category = typer.prompt("Enter new category name", type=str)
                add_category(new_category, db_path)
                selected_category = new_category
                console.print(f"[green]Added new category: {new_category}[/green]")
            else:
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(categories):
                        selected_category = categories[choice_idx]
                    else:
                        console.print("[red]Invalid choice, skipping[/red]\n")
                        continue
                except ValueError:
                    console.print("[red]Invalid input, skipping[/red]\n")
                    continue

            update_transaction_review(txn["id"], selected_category, db_path)
            console.print(f"[green]Categorized as: {selected_category}[/green]\n")

        console.print("[green]Review complete![/green]", style="bold")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


@app.command()
def status(
    sort_by: str = typer.Option("value", help="Sort by 'value' or 'alpha'"),
    histogram: bool = typer.Option(True, help="Show histogram visualization")
) -> None:
    """Show income and spending breakdown by category."""
    db_path = get_db_path()

    try:
        breakdown = get_category_breakdown(db_path)

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

        if expenses:
            console.print("[bold red]Expenses by category:[/bold red]\n")
            if histogram:
                max_amount = max(abs(amount) for _, amount in sorted_expenses)
                bar_width = 40

                for category, amount in sorted_expenses:
                    amount_display = f"£{abs(amount) / 100:,.2f}"
                    bar_length = int((abs(amount) / max_amount) * bar_width) if max_amount > 0 else 0
                    bar = "█" * bar_length
                    console.print(f"  {category:20} {amount_display:>12} {bar}")
            else:
                for category, amount in sorted_expenses:
                    console.print(f"  {category}: £{abs(amount) / 100:,.2f}")

            total_expenses = sum(expenses.values())
            console.print(f"\n  [bold]Total expenses:[/bold] £{abs(total_expenses) / 100:,.2f}\n")

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


if __name__ == "__main__":
    app()
