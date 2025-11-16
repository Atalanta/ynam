"""CLI entry point for ynam."""

import sqlite3
import sys

import requests
import typer
from rich.console import Console

from ynam.db import get_db_path, init_database, insert_transaction
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


if __name__ == "__main__":
    app()
