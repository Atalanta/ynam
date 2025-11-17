"""CLI entry point for ynam."""

import csv
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import typer
from rich.columns import Columns
from rich.console import Console
from rich.table import Table

from ynam.config import add_source, create_default_config, get_config_path, get_source, load_config
from ynam.db import (
    add_category,
    get_all_budgets,
    get_all_categories,
    get_all_transactions,
    get_auto_allocate_rule,
    get_auto_ignore_rule,
    get_category_breakdown,
    get_db_path,
    get_monthly_tbb,
    get_most_recent_transaction_date,
    get_suggested_category,
    get_transactions_by_category,
    get_unreviewed_transactions,
    init_database,
    insert_transaction,
    mark_transaction_ignored,
    set_auto_allocate_rule,
    set_auto_ignore_rule,
    set_budget,
    set_monthly_tbb,
    update_transaction_review,
)
from ynam.starling import get_account_info, get_transactions

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


@app.command(name="backup")
def backup_ynam(
    output_dir: str = typer.Option(None, "--output", "-o", help="Backup directory (default: ~/.ynam/backups)"),
) -> None:
    """Backup database and configuration files."""
    db_path = get_db_path()
    config_path = get_config_path()

    # Check if files exist
    if not db_path.exists():
        console.print("[red]Database not found. Run 'ynam init' first.[/red]", style="bold")
        sys.exit(1)

    if not config_path.exists():
        console.print("[red]Config not found. Run 'ynam init' first.[/red]", style="bold")
        sys.exit(1)

    # Determine backup directory
    if output_dir:
        backup_dir = Path(output_dir).expanduser()
    else:
        backup_dir = Path.home() / ".ynam" / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamp for backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Backup paths
    db_backup = backup_dir / f"ynam_{timestamp}.db"
    config_backup = backup_dir / f"config_{timestamp}.toml"

    try:
        import shutil

        # Copy database
        shutil.copy2(db_path, db_backup)
        console.print(f"[green]✓[/green] Database backed up to: {db_backup}")

        # Copy config
        shutil.copy2(config_path, config_backup)
        console.print(f"[green]✓[/green] Config backed up to: {config_backup}")

        console.print("\n[green]Backup complete![/green]", style="bold")
        console.print(f"[dim]Backup directory: {backup_dir}[/dim]")

    except OSError as e:
        console.print(f"[red]Backup failed: {e}[/red]", style="bold")
        sys.exit(1)


@app.command(name="init")
def init_ynam(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing database and config"),
) -> None:
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed duplicate report"),
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


def sync_api_source(
    source: dict[str, Any], db_path: Path, days_override: int | None = None, verbose: bool = False
) -> None:
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
        console.print(
            f"[red]API token not found. Set {token_env} environment variable or add 'token' to source config.[/red]",
            style="bold",
        )
        sys.exit(1)

    days = days_override if days_override is not None else source.get("days", 30)

    try:
        console.print("[cyan]Syncing from Starling Bank API...[/cyan]")
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
        duplicates: list[dict[str, Any]] = []

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
                    duplicates.append(
                        {"date": date, "description": description, "amount": amount, "duplicate_id": duplicate_id}
                    )

        console.print(f"[green]Successfully synced {inserted} transactions![/green]", style="bold")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print("\n[bold cyan]Duplicate Report:[/bold cyan]")
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

                    table.add_row(dup["date"], dup["description"][:50], amount_display, str(dup["duplicate_id"]))

                console.print(table)

    except requests.RequestException as e:
        console.print(f"[red]API error: {e}[/red]", style="bold")
        sys.exit(1)
    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


def sync_csv_source(source: dict[str, Any], db_path: Path, verbose: bool = False) -> None:
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

            console.print("\n[bold cyan]Suggested mapping:[/bold cyan]")
            console.print(f"  Date column: [yellow]{suggested['date'] or 'NOT DETECTED'}[/yellow]")
            console.print(f"  Description column: [yellow]{suggested['description'] or 'NOT DETECTED'}[/yellow]")
            console.print(f"  Amount column: [yellow]{suggested['amount'] or 'NOT DETECTED'}[/yellow]")

            console.print("\n[bold cyan]Sample row:[/bold cyan]")
            for key, value in list(transactions[0].items())[:5]:
                console.print(f"  {key}: {value}")

            console.print()
            date_input = typer.prompt("Date column name or number", default=suggested["date"] or "")
            desc_input = typer.prompt("Description column name or number", default=suggested["description"] or "")
            amount_input = typer.prompt("Amount column name or number", default=suggested["amount"] or "")

            # Validate inputs are not empty
            if not date_input or not desc_input or not amount_input:
                console.print("[red]All columns are required (date, description, amount)[/red]", style="bold")
                sys.exit(1)

            date_col = headers[int(date_input) - 1] if date_input.isdigit() else date_input
            desc_col = headers[int(desc_input) - 1] if desc_input.isdigit() else desc_input
            amount_col = headers[int(amount_input) - 1] if amount_input.isdigit() else amount_input

            source["date_column"] = date_col
            source["description_column"] = desc_col
            source["amount_column"] = amount_col

            add_source(source)
            console.print("\n[green]✓[/green] Source configuration saved")

        # At this point, we're guaranteed to have valid column names
        assert date_col and desc_col and amount_col, "Column names must be set"

        console.print(f"\n[cyan]Importing {len(transactions)} transactions as expenses...[/cyan]")

        inserted = 0
        skipped = 0
        duplicates: list[dict[str, Any]] = []

        for row in transactions:
            # Validate row data exists and is valid
            raw_date = row.get(date_col, "").strip()
            if not raw_date:
                console.print(f"[yellow]Skipping row with missing date: {row}[/yellow]")
                continue
            date = raw_date[:10]

            description = row.get(desc_col, "").strip() or "Unknown"

            raw_amount = row.get(amount_col, "").strip()
            if not raw_amount:
                console.print(f"[yellow]Skipping row with missing amount: {row}[/yellow]")
                continue

            try:
                amount = int(float(raw_amount) * 100)
            except ValueError:
                console.print(f"[yellow]Skipping row with invalid amount '{raw_amount}': {row}[/yellow]")
                continue

            amount = -abs(amount)

            success, duplicate_id = insert_transaction(date, description, amount, db_path)
            if success:
                inserted += 1
            else:
                skipped += 1
                if verbose:
                    duplicates.append(
                        {"date": date, "description": description, "amount": amount, "duplicate_id": duplicate_id}
                    )

        console.print(f"[green]Successfully synced {inserted} transactions![/green]", style="bold")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print("\n[bold cyan]Duplicate Report:[/bold cyan]")
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

                    table.add_row(dup["date"], dup["description"][:50], amount_display, str(dup["duplicate_id"]))

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
        Dictionary with suggested mappings for date, description, amount (empty string if not detected).
    """
    mappings: dict[str, str] = {
        "date": "",
        "description": "",
        "amount": "",
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

        console.print("\n[bold cyan]Suggested mapping:[/bold cyan]")
        console.print(f"  Date column: [yellow]{suggested['date'] or 'NOT DETECTED'}[/yellow]")
        console.print(f"  Description column: [yellow]{suggested['description'] or 'NOT DETECTED'}[/yellow]")
        console.print(f"  Amount column: [yellow]{suggested['amount'] or 'NOT DETECTED'}[/yellow]")

        console.print("\n[bold cyan]Sample row:[/bold cyan]")
        for key, value in list(transactions[0].items())[:5]:
            console.print(f"  {key}: {value}")

        console.print()
        date_input = typer.prompt("Date column name or number", default=suggested["date"] or "")
        desc_input = typer.prompt("Description column name or number", default=suggested["description"] or "")
        amount_input = typer.prompt("Amount column name or number", default=suggested["amount"] or "")

        # Validate inputs are not empty
        if not date_input or not desc_input or not amount_input:
            console.print("[red]All columns are required (date, description, amount)[/red]", style="bold")
            sys.exit(1)

        date_col = headers[int(date_input) - 1] if date_input.isdigit() else date_input
        desc_col = headers[int(desc_input) - 1] if desc_input.isdigit() else desc_input
        amount_col = headers[int(amount_input) - 1] if amount_input.isdigit() else amount_input

        console.print(f"\n[cyan]Importing {len(transactions)} transactions as expenses...[/cyan]")

        inserted = 0
        skipped = 0
        duplicates: list[dict[str, Any]] = []

        for row in transactions:
            # Validate row data exists and is valid
            raw_date = row.get(date_col, "").strip()
            if not raw_date:
                console.print(f"[yellow]Skipping row with missing date: {row}[/yellow]")
                continue
            date = raw_date[:10]

            description = row.get(desc_col, "").strip() or "Unknown"

            raw_amount = row.get(amount_col, "").strip()
            if not raw_amount:
                console.print(f"[yellow]Skipping row with missing amount: {row}[/yellow]")
                continue

            try:
                amount = int(float(raw_amount) * 100)
            except ValueError:
                console.print(f"[yellow]Skipping row with invalid amount '{raw_amount}': {row}[/yellow]")
                continue

            amount = -abs(amount)

            success, duplicate_id = insert_transaction(date, description, amount, db_path)
            if success:
                inserted += 1
            else:
                skipped += 1
                if verbose:
                    duplicates.append(
                        {"date": date, "description": description, "amount": amount, "duplicate_id": duplicate_id}
                    )

        console.print(f"[green]Successfully imported {inserted} transactions![/green]")
        if skipped > 0:
            console.print(f"[dim]Skipped {skipped} duplicates[/dim]")

            if verbose and duplicates:
                console.print("\n[bold cyan]Duplicate Report:[/bold cyan]")
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

                    table.add_row(dup["date"], dup["description"][:50], amount_display, str(dup["duplicate_id"]))

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
    all: bool = typer.Option(False, "--all", "-a", help="Show all transactions"),
) -> None:
    """List transactions."""
    db_path = get_db_path()

    try:
        actual_limit = None if all else limit
        transactions = get_all_transactions(db_path, actual_limit)

        if not transactions:
            console.print("[yellow]No transactions found[/yellow]")
            return

        title = (
            f"Transactions (showing all {len(transactions)})" if all else f"Transactions (showing {len(transactions)})"
        )
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

            table.add_row(txn["date"], txn["description"], amount_display, category, status)

        console.print(table)

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


def categorize_transaction(txn: dict[str, Any], db_path: Path) -> bool:
    """Categorize a single transaction.

    Args:
        txn: Transaction dictionary.
        db_path: Path to database.

    Returns:
        True if transaction was categorized or ignored, False if skipped or quit.
    """
    amount = txn["amount"]
    if amount < 0:
        amount_display = f"-£{abs(amount) / 100:.2f}"
    else:
        amount_display = f"+£{amount / 100:.2f}"

    console.print(f"[bold]Date:[/bold] {txn['date']}")
    console.print(f"[bold]Description:[/bold] {txn['description']}")
    console.print(f"[bold]Amount:[/bold] {amount_display}\n")

    categories = get_all_categories(db_path)
    suggested = get_suggested_category(txn["description"], db_path)

    if categories:
        console.print("[cyan]Categories:[/cyan]")
        category_items = [f"{idx}. {cat}" for idx, cat in enumerate(categories, 1)]
        console.print(Columns(category_items, equal=True, expand=False, column_first=True))
        console.print("  n. New category")

        if suggested:
            console.print(
                f"\n[yellow]Suggested:[/yellow] [bold]{suggested}[/bold] [dim](press Enter to accept, a to auto-allocate all)[/dim]"
            )
            prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, i to ignore, a to auto-allocate, q to quit)"
            choice = typer.prompt(prompt_text, type=str, default="")
        else:
            prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, i to ignore, q to quit)"
            choice = typer.prompt(prompt_text, type=str)
    else:
        console.print("[dim]No categories yet[/dim]")
        choice = typer.prompt("\nEnter category name (or s to skip, i to ignore, q to quit)", type=str)

    if choice.lower() == "q":
        console.print("[yellow]Exiting[/yellow]")
        return False

    if choice.lower() == "s":
        console.print("[dim]Skipped[/dim]\n")
        return False

    if choice.lower() == "i":
        mark_transaction_ignored(txn["id"], db_path)
        auto_ignore = typer.confirm("Always ignore transactions like this?", default=False)
        if auto_ignore:
            set_auto_ignore_rule(txn["description"], db_path)
            console.print("[dim]Ignored (will auto-ignore similar transactions)[/dim]\n")
        else:
            console.print("[dim]Ignored (excluded from reports)[/dim]\n")
        return True

    if choice.lower() == "a" and suggested:
        set_auto_allocate_rule(txn["description"], suggested, db_path)
        update_transaction_review(txn["id"], suggested, db_path)
        console.print(f"[green]Auto-allocating as: {suggested}[/green]\n")
        return True

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
                return False
        except ValueError:
            console.print("[red]Invalid input, skipping[/red]\n")
            return False

    update_transaction_review(txn["id"], selected_category, db_path)
    console.print(f"[green]Categorized as: {selected_category}[/green]\n")
    return True


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

            # Use helper function for manual categorization
            result = categorize_transaction(txn, db_path)
            if not result:
                # User chose 's' - check if they want session skip rule
                skip_all = typer.confirm("Skip all future transactions like this in this session?", default=False)
                if skip_all:
                    session_skip_rules[txn["description"]] = True
                    console.print("[dim]Will skip similar transactions this session[/dim]\n")

        console.print("[green]Review complete![/green]", style="bold")

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


@app.command()
def inspect(
    category: str,
    all: bool = typer.Option(False, "--all", "-a", help="Show all time (default: current month)"),
    month: str = typer.Option(None, "--month", help="Specific month (YYYY-MM)"),
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


@app.command(name="report")
def generate_report(
    sort_by: str = typer.Option("value", help="Sort by 'value' or 'alpha'"),
    histogram: bool = typer.Option(True, help="Show histogram visualization"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all time (default: current month)"),
    month: str = typer.Option(None, "--month", help="Specific month (YYYY-MM)"),
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
    source_spending = get_category_breakdown(db_path, since_date, until_date)

    # Calculate rollover for each category
    total_rollover = 0
    rollover_details = []

    for category, allocated in source_budgets.items():
        spent_pence = source_spending.get(category, 0)
        spent_abs = abs(spent_pence) if spent_pence < 0 else 0
        available = allocated - spent_abs

        if available > 0:
            total_rollover += available
            rollover_details.append((category, available))

    # Copy budgets to target month
    for category, allocated in source_budgets.items():
        set_budget(category, target_month, allocated, db_path)

    console.print(f"[green]✓ Copied {len(source_budgets)} category budgets[/green]")

    # Set TBB with rollover
    new_tbb = source_tbb + total_rollover
    set_monthly_tbb(target_month, new_tbb, db_path)

    console.print(f"\n[bold]Budget Summary for {month_display}:[/bold]")
    console.print(f"  Base TBB from {source_month_display}: £{source_tbb / 100:,.2f}")

    if rollover_details:
        console.print("\n[bold cyan]Rolled over unspent amounts:[/bold cyan]")
        for category, amount in rollover_details:
            console.print(f"  {category}: £{amount / 100:,.2f}")

    console.print(f"\n[bold]Total TBB for {month_display}: £{new_tbb / 100:,.2f}[/bold]")
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

            category = categories[idx]
            current_allocation = budgets[category]

            console.print(
                f"\n[bold]{category}[/bold] - Currently allocated: [cyan]£{current_allocation / 100:,.2f}[/cyan]"
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
                console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")
                console.print(f"[dim]Available TBB: £{remaining_tbb / 100:,.2f}[/dim]")
                amount_str = typer.prompt("Set budget to (£)", type=str)

                try:
                    target_pounds = float(amount_str)
                    target_pence = int(target_pounds * 100)

                    if target_pence < 0:
                        console.print("[red]Amount must be positive[/red]\n")
                        continue

                    # Calculate difference
                    difference = target_pence - current_allocation

                    # If increasing, check TBB availability
                    if difference > 0 and difference > remaining_tbb:
                        console.print(
                            f"[red]Not enough TBB. Need £{difference / 100:,.2f} but only £{remaining_tbb / 100:,.2f} available[/red]\n"
                        )
                        continue

                    # Update budget
                    set_budget(category, target_month, target_pence, db_path)
                    budgets[category] = target_pence

                    console.print(f"[green]✓ {category} now allocated: £{target_pence / 100:,.2f}[/green]")
                    if difference > 0:
                        console.print(f"[dim]Took £{difference / 100:,.2f} from TBB[/dim]\n")
                    elif difference < 0:
                        console.print(f"[dim]Returned £{abs(difference) / 100:,.2f} to TBB[/dim]\n")
                    else:
                        console.print("[dim]No change[/dim]\n")

                except ValueError:
                    console.print("[red]Invalid amount[/red]\n")

            elif action == "+":
                if remaining_tbb <= 0:
                    console.print("[red]No TBB remaining to add[/red]\n")
                    continue

                console.print(f"[dim]Available TBB: £{remaining_tbb / 100:,.2f}[/dim]")
                amount_str = typer.prompt("Amount to add (£)", type=str)

                try:
                    amount_pounds = float(amount_str)
                    amount_pence = int(amount_pounds * 100)

                    if amount_pence <= 0:
                        console.print("[red]Amount must be positive[/red]\n")
                        continue

                    if amount_pence > remaining_tbb:
                        console.print(f"[red]Not enough TBB (only £{remaining_tbb / 100:,.2f} available)[/red]\n")
                        continue

                    new_allocation = current_allocation + amount_pence
                    set_budget(category, target_month, new_allocation, db_path)
                    budgets[category] = new_allocation
                    console.print(f"[green]✓ {category} now allocated: £{new_allocation / 100:,.2f}[/green]\n")

                except ValueError:
                    console.print("[red]Invalid amount[/red]\n")

            elif action == "-":
                if current_allocation <= 0:
                    console.print("[red]No allocation to remove[/red]\n")
                    continue

                console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")
                amount_str = typer.prompt("Amount to remove (£)", type=str)

                try:
                    amount_pounds = float(amount_str)
                    amount_pence = int(amount_pounds * 100)

                    if amount_pence <= 0:
                        console.print("[red]Amount must be positive[/red]\n")
                        continue

                    if amount_pence > current_allocation:
                        console.print(
                            f"[red]Can't remove more than allocated (only £{current_allocation / 100:,.2f})[/red]\n"
                        )
                        continue

                    new_allocation = current_allocation - amount_pence
                    set_budget(category, target_month, new_allocation, db_path)
                    budgets[category] = new_allocation
                    console.print(f"[green]✓ {category} now allocated: £{new_allocation / 100:,.2f}[/green]")
                    console.print(f"[dim]Returned £{amount_pence / 100:,.2f} to TBB[/dim]\n")

                except ValueError:
                    console.print("[red]Invalid amount[/red]\n")

            elif action.lower() == "t":
                console.print("\nTransfer to:")
                other_categories = [cat for cat in categories if cat != category]
                for idx2, cat in enumerate(other_categories, 1):
                    console.print(f"  {idx2}. {cat}")

                target_choice = typer.prompt(f"\nSelect target category (1-{len(other_categories)})", type=str)

                try:
                    target_idx = int(target_choice) - 1
                    if target_idx < 0 or target_idx >= len(other_categories):
                        console.print("[red]Invalid selection[/red]\n")
                        continue

                    target_category = other_categories[target_idx]

                    console.print(f"[dim]Current allocation: £{current_allocation / 100:,.2f}[/dim]")
                    amount_str = typer.prompt("Amount to transfer (£)", type=str)

                    amount_pounds = float(amount_str)
                    amount_pence = int(amount_pounds * 100)

                    if amount_pence <= 0:
                        console.print("[red]Amount must be positive[/red]\n")
                        continue

                    if amount_pence > current_allocation:
                        console.print(
                            f"[red]Can't transfer more than allocated (only £{current_allocation / 100:,.2f})[/red]\n"
                        )
                        continue

                    # Update source category
                    new_source = current_allocation - amount_pence
                    set_budget(category, target_month, new_source, db_path)
                    budgets[category] = new_source

                    # Update target category
                    target_current = budgets.get(target_category, 0)
                    new_target = target_current + amount_pence
                    set_budget(target_category, target_month, new_target, db_path)
                    budgets[target_category] = new_target

                    console.print(
                        f"[green]✓ Transferred £{amount_pence / 100:,.2f} from {category} to {target_category}[/green]"
                    )
                    console.print(f"  {category}: £{new_source / 100:,.2f}")
                    console.print(f"  {target_category}: £{new_target / 100:,.2f}\n")

                except (ValueError, IndexError):
                    console.print("[red]Invalid input[/red]\n")

            else:
                console.print("[red]Invalid option[/red]\n")

        except ValueError:
            console.print("[red]Invalid selection[/red]\n")


@app.command()
def budget(
    set_tbb: float = typer.Option(None, "--set-tbb", help="Set To Be Budgeted amount for the month (in £)"),
    status: bool = typer.Option(False, "--status", help="Show budget status and spending"),
    adjust: bool = typer.Option(False, "--adjust", help="Adjust budget allocations interactively"),
    copy_from: str = typer.Option(
        None, "--copy-from", help="Copy budget from month (YYYY-MM), rolling over unspent amounts"
    ),
    from_cat: str = typer.Option(None, "--from", help="Source category (name, index, or 'TBB')"),
    to_cat: str = typer.Option(None, "--to", help="Target category (name, index, or 'TBB')"),
    amount: float = typer.Option(None, "--amount", help="Amount to transfer (in £)"),
    month: str = typer.Option(None, "--month", help="Month to budget for (YYYY-MM, default: current month)"),
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
        categories = get_all_categories(db_path)

        if not categories:
            console.print(
                "[yellow]No categories found. Create some categories first by reviewing transactions.[/yellow]"
            )
            return

        # Get TBB for the month
        tbb_pence = get_monthly_tbb(target_month, db_path)
        if tbb_pence is None:
            console.print(f"[yellow]No TBB set for {month_display}. Use --set-tbb to set it first.[/yellow]")
            return

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

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)


if __name__ == "__main__":
    app()
