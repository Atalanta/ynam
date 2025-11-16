"""CLI entry point for ynam."""

import sqlite3
import sys

import typer
from rich.console import Console

from ynam.db import get_db_path, init_database

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


if __name__ == "__main__":
    app()
