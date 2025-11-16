"""CLI entry point for ynam."""

import sqlite3
import sys

import requests
import typer
from rich.console import Console

from ynam.db import (
    get_category_breakdown,
    get_db_path,
    get_unreviewed_transactions,
    init_database,
    insert_transaction,
    update_transaction_review,
)
from ynam.starling import get_account_balance, get_account_info, get_token, get_transactions

app = typer.Typer(
    name="ynam",
    help="You Need A Mirror - A YNAB-inspired money management tool",
    add_completion=False,
)
console = Console()

CATEGORIES = [
    "fixed mandatory",
    "variable mandatory",
    "fixed discretionary",
    "variable discretionary",
]


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
def fetch() -> None:
    """Fetch transactions from Starling Bank API."""
    token = get_token()
    if not token:
        console.print("[red]STARLING_TOKEN environment variable not set[/red]", style="bold")
        sys.exit(1)

    db_path = get_db_path()

    try:
        console.print("[cyan]Fetching account information...[/cyan]")
        account_uid, category_uid = get_account_info(token)

        console.print("[cyan]Fetching transactions...[/cyan]")
        transactions = get_transactions(token, account_uid, category_uid)

        console.print(f"[cyan]Inserting {len(transactions)} transactions...[/cyan]")
        for txn in transactions:
            date = txn["transactionTime"][:10]
            description = txn.get("counterPartyName", "Unknown")
            amount = int(txn["amount"]["minorUnits"])
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

    try:
        transactions = get_unreviewed_transactions(db_path)

        if not transactions:
            console.print("[yellow]No unreviewed transactions found[/yellow]")
            return

        console.print(f"[cyan]Found {len(transactions)} unreviewed transactions[/cyan]\n")

        for txn in transactions:
            amount_display = f"£{txn['amount'] / 100:.2f}"
            console.print(f"[bold]Date:[/bold] {txn['date']}")
            console.print(f"[bold]Description:[/bold] {txn['description']}")
            console.print(f"[bold]Amount:[/bold] {amount_display}\n")

            console.print("[cyan]Categories:[/cyan]")
            for idx, cat in enumerate(CATEGORIES, 1):
                console.print(f"  {idx}. {cat}")

            choice = typer.prompt("\nSelect category (1-4, or 's' to skip)", type=str)

            if choice.lower() == "s":
                console.print("[dim]Skipped[/dim]\n")
                continue

            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(CATEGORIES):
                    selected_category = CATEGORIES[choice_idx]
                    update_transaction_review(txn["id"], selected_category, db_path)
                    console.print(f"[green]Categorized as: {selected_category}[/green]\n")
                else:
                    console.print("[red]Invalid choice, skipping[/red]\n")
            except ValueError:
                console.print("[red]Invalid input, skipping[/red]\n")

        console.print("[green]Review complete![/green]", style="bold")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


@app.command()
def status() -> None:
    """Show account balance and spending breakdown."""
    token = get_token()
    if not token:
        console.print("[red]STARLING_TOKEN environment variable not set[/red]", style="bold")
        sys.exit(1)

    db_path = get_db_path()

    try:
        account_uid, _ = get_account_info(token)
        api_balance = get_account_balance(token, account_uid)
        console.print(f"[bold]Account balance:[/bold] £{api_balance / 100:.2f}\n")

        breakdown = get_category_breakdown(db_path)

        if breakdown:
            console.print("[bold cyan]Spending by category:[/bold cyan]")
            for category, amount in breakdown.items():
                console.print(f"  {category}: £{amount / 100:.2f}")
        else:
            console.print("[dim]No categorized transactions yet[/dim]")

    except requests.RequestException as e:
        console.print(f"[red]API error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


if __name__ == "__main__":
    app()
