"""CLI entry point for ynam."""

import csv
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
import typer
from rich.columns import Columns
from rich.console import Console
from rich.table import Table

from ynam.config import add_source, create_default_config, get_config_path, get_source, load_config
from ynam.db import (
    add_category,
    get_all_categories,
    get_all_transactions,
    get_auto_allocate_rule,
    get_auto_ignore_rule,
    get_category_breakdown,
    get_db_path,
    get_most_recent_transaction_date,
    get_suggested_category,
    get_unreviewed_transactions,
    init_database,
    insert_transaction,
    mark_transaction_ignored,
    set_auto_allocate_rule,
    set_auto_ignore_rule,
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


@app.command(name="init")
def init_ynam(force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing database and config")) -> None:
    """Initialize ynam database and configuration."""
    db_path = get_db_path()
    config_path = get_config_path()

    db_exists = db_path.exists()
    config_exists = config_path.exists()

    if not force and (db_exists or config_exists):
        console.print("[red]Initialization failed:[/red]", style="bold")
        if db_exists:
            console.print(f"  Database already exists: {db_path}")
        if config_exists:
            console.print(f"  Config already exists: {config_path}")
        console.print("\n[yellow]Use 'ynam init --force' to overwrite[/yellow]")
        sys.exit(1)

    try:
        console.print(f"[cyan]Initializing database at {db_path}...[/cyan]")
        init_database(db_path)
        console.print("[green]✓[/green] Database initialized")

        console.print(f"[cyan]Creating config file at {config_path}...[/cyan]")
        create_default_config(config_path)
        console.print("[green]✓[/green] Config file created (permissions: 600)")

        console.print("\n[green]Initialization complete![/green]", style="bold")
        console.print(f"[dim]Database: {db_path}[/dim]")
        console.print(f"[dim]Config: {config_path}[/dim]")

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
def sync(
    source_name_or_path: str,
    days: int = typer.Option(None, "--days", help="Number of days to fetch (overrides config)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed duplicate report")
) -> None:
    """Sync transactions from a configured source or CSV file path."""
    db_path = get_db_path()

    csv_path = Path(source_name_or_path).expanduser()
    if csv_path.exists() and csv_path.suffix.lower() == ".csv":
        sync_new_csv_file(csv_path, db_path, verbose)
        return

    try:
        source = get_source(source_name_or_path)
    except FileNotFoundError:
        console.print("[red]Config file not found. Run 'ynam init' first.[/red]", style="bold")
        sys.exit(1)

    if not source:
        console.print(f"[red]Source '{source_name_or_path}' not found in config.[/red]", style="bold")
        console.print("\n[yellow]Available sources:[/yellow]")

        try:
            config = load_config()
            sources = config.get("sources", [])

            if sources:
                for src in sources:
                    console.print(f"  • {src['name']} ({src['type']})")
            else:
                console.print("  [dim]No sources configured yet[/dim]")
                console.print("\n[cyan]Add a source to your config file at:[/cyan]")
                console.print(f"  {get_config_path()}")
        except Exception:
            pass

        sys.exit(1)

    source_type = source.get("type")

    if source_type == "api":
        sync_api_source(source, db_path, days, verbose)
    elif source_type == "csv":
        sync_csv_source(source, db_path, verbose)
    else:
        console.print(f"[red]Unknown source type: {source_type}[/red]", style="bold")
        sys.exit(1)


def sync_api_source(source: dict, db_path: Path, days_override: int = None, verbose: bool = False) -> None:
    """Sync transactions from API source.

    Args:
        source: Source configuration dict.
        db_path: Path to database.
        days_override: Optional override for number of days to fetch.
        verbose: Show detailed duplicate report.
    """
    provider = source.get("provider")

    if provider != "starling":
        console.print(f"[red]Unknown API provider: {provider}[/red]", style="bold")
        sys.exit(1)

    token_env = source.get("token_env")
    token = source.get("token") or (os.environ.get(token_env) if token_env else None)

    if not token:
        console.print(f"[red]API token not found. Set {token_env} environment variable or add 'token' to source config.[/red]", style="bold")
        sys.exit(1)

    days = days_override if days_override is not None else source.get("days", 30)

    try:
        console.print(f"[cyan]Syncing from Starling Bank API...[/cyan]")
        account_uid, category_uid = get_account_info(token)

        if days_override is not None:
            since_date = datetime.now() - timedelta(days=days)
            console.print(f"[cyan]Fetching transactions from last {days} days (override)...[/cyan]")
        else:
            most_recent_date = get_most_recent_transaction_date(db_path)
            if most_recent_date:
                since_date = datetime.fromisoformat(most_recent_date) - timedelta(days=1)
                console.print(f"[cyan]Fetching transactions since {most_recent_date} (with 1 day overlap)...[/cyan]")
            else:
                since_date = datetime.now() - timedelta(days=days)
                console.print(f"[cyan]Fetching transactions from last {days} days...[/cyan]")

        transactions = get_transactions(token, account_uid, category_uid, since_date)

        console.print(f"[cyan]Inserting {len(transactions)} transactions...[/cyan]")
        inserted = 0
        skipped = 0
        duplicates = []

        for txn in transactions:
            date = txn["transactionTime"][:10]
            description = txn.get("counterPartyName", "Unknown")
            amount = int(txn["amount"]["minorUnits"])

            if txn.get("direction") == "OUT":
                amount = -amount

            success, duplicate_id = insert_transaction(date, description, amount, db_path)
            if success:
                inserted += 1
            else:
                skipped += 1
                if verbose:
                    duplicates.append({
                        "date": date,
                        "description": description,
                        "amount": amount,
                        "duplicate_id": duplicate_id
                    })

        console.print(f"[green]Successfully synced {inserted} transactions![/green]", style="bold")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print(f"\n[bold cyan]Duplicate Report:[/bold cyan]")
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Date")
                table.add_column("Description")
                table.add_column("Amount", justify="right")
                table.add_column("Matches DB ID", justify="center")

                for dup in duplicates:
                    amount_val = dup["amount"]
                    if amount_val < 0:
                        amount_display = f"-£{abs(amount_val) / 100:,.2f}"
                    else:
                        amount_display = f"+£{amount_val / 100:,.2f}"

                    table.add_row(
                        dup["date"],
                        dup["description"][:50],
                        amount_display,
                        str(dup["duplicate_id"])
                    )

                console.print(table)

    except requests.RequestException as e:
        console.print(f"[red]API error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


def sync_csv_source(source: dict, db_path: Path, verbose: bool = False) -> None:
    """Sync transactions from CSV source.

    Args:
        source: Source configuration dict.
        db_path: Path to database.
        verbose: Show detailed duplicate report.
    """
    csv_path = Path(source.get("path", "")).expanduser()

    if not csv_path.exists():
        console.print(f"[red]CSV file not found: {csv_path}[/red]", style="bold")
        sys.exit(1)

    try:
        console.print(f"[cyan]Reading CSV file: {csv_path}...[/cyan]")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            transactions = list(reader)

        if not transactions:
            console.print("[yellow]No transactions found in CSV[/yellow]")
            return

        date_col = source.get("date_column")
        desc_col = source.get("description_column")
        amount_col = source.get("amount_column")

        if not all([date_col, desc_col, amount_col]):
            console.print("[yellow]Source not fully configured. Running interactive setup...[/yellow]\n")

            headers = list(transactions[0].keys())
            suggested = analyze_csv_columns(headers)

            console.print("[bold cyan]CSV columns detected:[/bold cyan]")
            for i, header in enumerate(headers, 1):
                console.print(f"  {i}. {header}")

            console.print(f"\n[bold cyan]Suggested mapping:[/bold cyan]")
            console.print(f"  Date column: [yellow]{suggested['date'] or 'NOT DETECTED'}[/yellow]")
            console.print(f"  Description column: [yellow]{suggested['description'] or 'NOT DETECTED'}[/yellow]")
            console.print(f"  Amount column: [yellow]{suggested['amount'] or 'NOT DETECTED'}[/yellow]")

            console.print(f"\n[bold cyan]Sample row:[/bold cyan]")
            for key, value in list(transactions[0].items())[:5]:
                console.print(f"  {key}: {value}")

            console.print()
            date_input = typer.prompt("Date column name or number", default=suggested["date"] or "")
            desc_input = typer.prompt("Description column name or number", default=suggested["description"] or "")
            amount_input = typer.prompt("Amount column name or number", default=suggested["amount"] or "")

            date_col = headers[int(date_input) - 1] if date_input.isdigit() else date_input
            desc_col = headers[int(desc_input) - 1] if desc_input.isdigit() else desc_input
            amount_col = headers[int(amount_input) - 1] if amount_input.isdigit() else amount_input

            source["date_column"] = date_col
            source["description_column"] = desc_col
            source["amount_column"] = amount_col

            add_source(source)
            console.print(f"\n[green]✓[/green] Source configuration saved")

        console.print(f"\n[cyan]Importing {len(transactions)} transactions as expenses...[/cyan]")

        inserted = 0
        skipped = 0
        duplicates = []

        for row in transactions:
            date = row[date_col][:10] if date_col else None
            description = row[desc_col] if desc_col else "Unknown"
            amount = int(float(row[amount_col]) * 100) if amount_col else 0
            amount = -abs(amount)

            success, duplicate_id = insert_transaction(date, description, amount, db_path)
            if success:
                inserted += 1
            else:
                skipped += 1
                if verbose:
                    duplicates.append({
                        "date": date,
                        "description": description,
                        "amount": amount,
                        "duplicate_id": duplicate_id
                    })

        console.print(f"[green]Successfully synced {inserted} transactions![/green]", style="bold")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print(f"\n[bold cyan]Duplicate Report:[/bold cyan]")
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Date")
                table.add_column("Description")
                table.add_column("Amount", justify="right")
                table.add_column("Matches DB ID", justify="center")

                for dup in duplicates:
                    amount_val = dup["amount"]
                    if amount_val < 0:
                        amount_display = f"-£{abs(amount_val) / 100:,.2f}"
                    else:
                        amount_display = f"+£{amount_val / 100:,.2f}"

                    table.add_row(
                        dup["date"],
                        dup["description"][:50],
                        amount_display,
                        str(dup["duplicate_id"])
                    )

                console.print(table)

        console.print("[dim]Note: During review, use 'i' to ignore payments/transfers (excluded from reports)[/dim]")

    except KeyError as e:
        console.print(f"[red]CSV format error: missing column {e}[/red]", style="bold")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Data format error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


def analyze_csv_columns(headers: list[str]) -> dict[str, str]:
    """Analyze CSV headers and suggest column mappings.

    Args:
        headers: List of CSV column names.

    Returns:
        Dictionary with suggested mappings for date, description, amount.
    """
    mappings = {
        "date": None,
        "description": None,
        "amount": None,
    }

    headers_lower = [h.lower() for h in headers]

    for i, header in enumerate(headers_lower):
        if not mappings["date"] and "date" in header:
            mappings["date"] = headers[i]

        if not mappings["description"]:
            if "merchant" in header and "name" in header:
                mappings["description"] = headers[i]
            elif "description" in header:
                mappings["description"] = headers[i]

        if not mappings["amount"] and "amount" in header and "currency" not in header:
            mappings["amount"] = headers[i]

    return mappings


def sync_new_csv_file(csv_path: Path, db_path: Path, verbose: bool = False) -> None:
    """Sync transactions from a new CSV file with interactive setup.

    Args:
        csv_path: Path to the CSV file.
        db_path: Path to the SQLite database.
        verbose: Show detailed duplicate report.
    """
    try:
        console.print(f"[cyan]Reading CSV file: {csv_path}...[/cyan]")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            transactions = list(reader)

        if not transactions:
            console.print("[yellow]No transactions found in CSV[/yellow]")
            return

        headers = list(transactions[0].keys())
        suggested = analyze_csv_columns(headers)

        console.print("\n[bold cyan]CSV columns detected:[/bold cyan]")
        for i, header in enumerate(headers, 1):
            console.print(f"  {i}. {header}")

        console.print(f"\n[bold cyan]Suggested mapping:[/bold cyan]")
        console.print(f"  Date column: [yellow]{suggested['date'] or 'NOT DETECTED'}[/yellow]")
        console.print(f"  Description column: [yellow]{suggested['description'] or 'NOT DETECTED'}[/yellow]")
        console.print(f"  Amount column: [yellow]{suggested['amount'] or 'NOT DETECTED'}[/yellow]")

        console.print(f"\n[bold cyan]Sample row:[/bold cyan]")
        for key, value in list(transactions[0].items())[:5]:
            console.print(f"  {key}: {value}")

        console.print()
        date_input = typer.prompt("Date column name or number", default=suggested["date"] or "")
        desc_input = typer.prompt("Description column name or number", default=suggested["description"] or "")
        amount_input = typer.prompt("Amount column name or number", default=suggested["amount"] or "")

        date_col = headers[int(date_input) - 1] if date_input.isdigit() else date_input
        desc_col = headers[int(desc_input) - 1] if desc_input.isdigit() else desc_input
        amount_col = headers[int(amount_input) - 1] if amount_input.isdigit() else amount_input

        console.print(f"\n[cyan]Importing {len(transactions)} transactions as expenses...[/cyan]")

        inserted = 0
        skipped = 0
        duplicates = []

        for row in transactions:
            date = row[date_col][:10] if date_col else None
            description = row[desc_col] if desc_col else "Unknown"
            amount = int(float(row[amount_col]) * 100) if amount_col else 0
            amount = -abs(amount)

            success, duplicate_id = insert_transaction(date, description, amount, db_path)
            if success:
                inserted += 1
            else:
                skipped += 1
                if verbose:
                    duplicates.append({
                        "date": date,
                        "description": description,
                        "amount": amount,
                        "duplicate_id": duplicate_id
                    })

        console.print(f"[green]Successfully imported {inserted} transactions![/green]")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print(f"\n[bold cyan]Duplicate Report:[/bold cyan]")
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Date")
                table.add_column("Description")
                table.add_column("Amount", justify="right")
                table.add_column("Matches DB ID", justify="center")

                for dup in duplicates:
                    amount_val = dup["amount"]
                    if amount_val < 0:
                        amount_display = f"-£{abs(amount_val) / 100:,.2f}"
                    else:
                        amount_display = f"+£{amount_val / 100:,.2f}"

                    table.add_row(
                        dup["date"],
                        dup["description"][:50],
                        amount_display,
                        str(dup["duplicate_id"])
                    )

                console.print(table)

        console.print("[dim]Note: During review, use 'i' to ignore payments/transfers (excluded from reports)[/dim]\n")

        save_source = typer.confirm("Save this CSV as a named source for future syncs?", default=True)
        if save_source:
            source_name = typer.prompt("Enter a name for this source")

            new_source = {
                "name": source_name,
                "type": "csv",
                "path": str(csv_path),
                "date_column": date_col,
                "description_column": desc_col,
                "amount_column": amount_col,
            }

            add_source(new_source)
            console.print(f"[green]✓[/green] Source '{source_name}' saved to config")
            console.print(f"[dim]Next time use: ynam sync {source_name}[/dim]")

    except KeyError as e:
        console.print(f"[red]CSV format error: missing column {e}[/red]", style="bold")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Data format error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


@app.command(name="list")
def list_transactions(
    limit: int = typer.Option(50, help="Maximum number of transactions to show"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all transactions")
) -> None:
    """List transactions."""
    db_path = get_db_path()

    try:
        actual_limit = None if all else limit
        transactions = get_all_transactions(db_path, actual_limit)

        if not transactions:
            console.print("[yellow]No transactions found[/yellow]")
            return

        title = f"Transactions (showing all {len(transactions)})" if all else f"Transactions (showing {len(transactions)})"
        table = Table(title=title)
        table.add_column("Date", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Amount", justify="right")
        table.add_column("Category", style="magenta")
        table.add_column("Status", justify="center")

        for txn in transactions:
            amount = txn["amount"]
            if amount < 0:
                amount_display = f"[red]-£{abs(amount) / 100:,.2f}[/red]"
            else:
                amount_display = f"[green]+£{amount / 100:,.2f}[/green]"

            category = txn.get("category") or "[dim]-[/dim]"

            if txn.get("ignored"):
                status = "⊗"
            elif txn["reviewed"]:
                status = "✓"
            else:
                status = "○"

            table.add_row(
                txn["date"],
                txn["description"],
                amount_display,
                category,
                status
            )

        console.print(table)

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

            if get_auto_ignore_rule(txn["description"], db_path):
                mark_transaction_ignored(txn["id"], db_path)
                console.print("[dim]Auto-ignoring (excluded from reports)[/dim]\n")
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
                    prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, i to ignore, a to auto-allocate, q to quit)"
                    choice = typer.prompt(prompt_text, type=str, default="")
                else:
                    prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, i to ignore, q to quit)"
                    choice = typer.prompt(prompt_text, type=str)
            else:
                console.print("[dim]No categories yet[/dim]")
                choice = typer.prompt("\nEnter category name (or s to skip, i to ignore, q to quit)", type=str)

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

            if choice.lower() == "i":
                mark_transaction_ignored(txn["id"], db_path)
                auto_ignore = typer.confirm("Always ignore transactions like this?", default=False)
                if auto_ignore:
                    set_auto_ignore_rule(txn["description"], db_path)
                    console.print("[dim]Ignored (will auto-ignore similar transactions)[/dim]\n")
                else:
                    console.print("[dim]Ignored (excluded from reports)[/dim]\n")
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


@app.command(name="report")
def generate_report(
    sort_by: str = typer.Option("value", help="Sort by 'value' or 'alpha'"),
    histogram: bool = typer.Option(True, help="Show histogram visualization")
) -> None:
    """Generate income and spending breakdown report."""
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
