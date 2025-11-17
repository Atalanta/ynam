"""Sync command for importing transactions."""

import csv
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import typer
from rich.console import Console
from rich.table import Table

from ynam.config import add_source, get_config_path, get_source, load_config
from ynam.db import get_db_path, get_most_recent_transaction_date, insert_transaction
from ynam.domain.transactions import CsvMapping, ParsedTransaction, analyze_csv_columns, parse_csv_transaction
from ynam.starling import get_account_info, get_transactions

console = Console()


@dataclass
class ImportStats:
    """Statistics from importing transactions."""

    inserted: int
    skipped: int
    duplicates: list[dict[str, Any]]


def resolve_sync_source(source_name_or_path: str) -> tuple[Path, None] | tuple[None, dict[str, Any]]:
    """Resolve whether argument is a CSV file path or configured source name.

    Args:
        source_name_or_path: Either a file path to CSV or a source name from config.

    Returns:
        Tuple of (csv_path, None) if CSV file, or (None, source_config) if configured source.

    Raises:
        SystemExit: If source not found or config issues.
    """
    csv_path = Path(source_name_or_path).expanduser()
    if csv_path.exists() and csv_path.suffix.lower() == ".csv":
        return csv_path, None

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

    return None, source


def compute_since_date(db_path: Path, days_override: int | None, default_days: int) -> datetime:
    """Compute the since_date for Starling API transaction fetch.

    Args:
        db_path: Path to database.
        days_override: Optional override for number of days.
        default_days: Default number of days if no override.

    Returns:
        Datetime to use as since_date for API query.
    """
    if days_override is not None:
        console.print(f"[cyan]Fetching transactions from last {days_override} days (override)...[/cyan]")
        return datetime.now() - timedelta(days=days_override)

    most_recent_date = get_most_recent_transaction_date(db_path)
    if most_recent_date:
        console.print(f"[cyan]Fetching transactions since {most_recent_date} (with 1 day overlap)...[/cyan]")
        return datetime.fromisoformat(most_recent_date) - timedelta(days=1)

    console.print(f"[cyan]Fetching transactions from last {default_days} days...[/cyan]")
    return datetime.now() - timedelta(days=default_days)


def render_duplicate_report(duplicates: list[dict[str, Any]]) -> None:
    """Render duplicate transactions report table.

    Args:
        duplicates: List of duplicate transaction dictionaries.
    """
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


def prompt_for_csv_mapping(headers: list[str], suggested: dict[str, str]) -> CsvMapping:
    """Interactively prompt user for CSV column mapping.

    Args:
        headers: List of CSV column names.
        suggested: Suggested mapping from analyze_csv_columns.

    Returns:
        CsvMapping with user-confirmed column names.

    Raises:
        SystemExit: If user provides invalid input.
    """
    console.print("[bold cyan]CSV columns detected:[/bold cyan]")
    for i, header in enumerate(headers, 1):
        console.print(f"  {i}. {header}")

    console.print("\n[bold cyan]Suggested mapping:[/bold cyan]")
    console.print(f"  Date column: [yellow]{suggested['date'] or 'NOT DETECTED'}[/yellow]")
    console.print(f"  Description column: [yellow]{suggested['description'] or 'NOT DETECTED'}[/yellow]")
    console.print(f"  Amount column: [yellow]{suggested['amount'] or 'NOT DETECTED'}[/yellow]")

    console.print()
    date_input = typer.prompt("Date column name or number", default=suggested["date"] or "")
    desc_input = typer.prompt("Description column name or number", default=suggested["description"] or "")
    amount_input = typer.prompt("Amount column name or number", default=suggested["amount"] or "")

    # Validate inputs are not empty
    if not date_input or not desc_input or not amount_input:
        console.print("[red]All columns are required (date, description, amount)[/red]", style="bold")
        sys.exit(1)

    # Resolve column names from numbers or names
    date_col = headers[int(date_input) - 1] if date_input.isdigit() else date_input
    desc_col = headers[int(desc_input) - 1] if desc_input.isdigit() else desc_input
    amount_col = headers[int(amount_input) - 1] if amount_input.isdigit() else amount_input

    return CsvMapping(date_column=date_col, description_column=desc_col, amount_column=amount_col)


def insert_parsed_transactions(transactions: list[ParsedTransaction], db_path: Path, verbose: bool) -> ImportStats:
    """Insert parsed transactions into database.

    Args:
        transactions: List of parsed transactions to insert.
        db_path: Path to database.
        verbose: Whether to track duplicates for reporting.

    Returns:
        ImportStats with insertion results.
    """
    inserted = 0
    skipped = 0
    duplicates: list[dict[str, Any]] = []

    for txn in transactions:
        success, duplicate_id = insert_transaction(txn["date"], txn["description"], txn["amount"], db_path)
        if success:
            inserted += 1
        else:
            skipped += 1
            if verbose:
                duplicates.append(
                    {
                        "date": txn["date"],
                        "description": txn["description"],
                        "amount": txn["amount"],
                        "duplicate_id": duplicate_id,
                    }
                )

    return ImportStats(inserted=inserted, skipped=skipped, duplicates=duplicates)


def sync_command(
    source_name_or_path: str,
    days: int | None = None,
    verbose: bool = False,
) -> None:
    """Sync transactions from a configured source or CSV file path."""
    db_path = get_db_path()

    csv_path, source = resolve_sync_source(source_name_or_path)

    if csv_path:
        sync_new_csv_file(csv_path, db_path, verbose)
        return

    assert source is not None, "source must be set if csv_path is None"
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

        since_date = compute_since_date(db_path, days_override, days)
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
                render_duplicate_report(duplicates)

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
            csv_rows = list(reader)

        if not csv_rows:
            console.print("[yellow]No transactions found in CSV[/yellow]")
            return

        date_col = source.get("date_column")
        desc_col = source.get("description_column")
        amount_col = source.get("amount_column")

        if not all([date_col, desc_col, amount_col]):
            console.print("[yellow]Source not fully configured. Running interactive setup...[/yellow]\n")

            headers = list(csv_rows[0].keys())
            suggested = analyze_csv_columns(headers)

            console.print("\n[bold cyan]Sample row:[/bold cyan]")
            for key, value in list(csv_rows[0].items())[:5]:
                console.print(f"  {key}: {value}")
            console.print()

            mapping = prompt_for_csv_mapping(headers, suggested)

            date_col = mapping["date_column"]
            desc_col = mapping["description_column"]
            amount_col = mapping["amount_column"]

            source["date_column"] = date_col
            source["description_column"] = desc_col
            source["amount_column"] = amount_col

            add_source(source)
            console.print("\n[green]✓[/green] Source configuration saved")

        # At this point, we're guaranteed to have valid column names
        assert date_col and desc_col and amount_col, "Column names must be set"

        # Create mapping for parsing
        mapping = CsvMapping(date_column=date_col, description_column=desc_col, amount_column=amount_col)

        # Parse transactions using domain function
        console.print(f"\n[cyan]Importing {len(csv_rows)} transactions as expenses...[/cyan]")
        parsed_transactions: list[ParsedTransaction] = []
        for row in csv_rows:
            parsed = parse_csv_transaction(row, mapping)
            if parsed:
                parsed_transactions.append(parsed)
            else:
                console.print(f"[yellow]Skipping invalid row: {row}[/yellow]")

        # Insert parsed transactions
        stats = insert_parsed_transactions(parsed_transactions, db_path, verbose)

        # Display results
        console.print(f"[green]Successfully synced {stats.inserted} transactions![/green]", style="bold")
        if stats.skipped > 0:
            console.print(f"[dim]Skipped {stats.skipped} duplicates[/dim]")
            if verbose and stats.duplicates:
                render_duplicate_report(stats.duplicates)

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


def sync_new_csv_file(csv_path: Path, db_path: Path, verbose: bool = False) -> None:
    """Sync transactions from a new CSV file with interactive setup.

    Args:
        csv_path: Path to the CSV file.
        db_path: Path to the SQLite database.
        verbose: Show detailed duplicate report.
    """
    try:
        # Read CSV file
        console.print(f"[cyan]Reading CSV file: {csv_path}...[/cyan]")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)

        if not csv_rows:
            console.print("[yellow]No transactions found in CSV[/yellow]")
            return

        # Infer and prompt for mapping
        headers = list(csv_rows[0].keys())
        suggested = analyze_csv_columns(headers)

        console.print("\n[bold cyan]Sample row:[/bold cyan]")
        for key, value in list(csv_rows[0].items())[:5]:
            console.print(f"  {key}: {value}")
        console.print()

        mapping = prompt_for_csv_mapping(headers, suggested)

        # Parse transactions using domain function
        console.print(f"\n[cyan]Importing {len(csv_rows)} transactions as expenses...[/cyan]")
        parsed_transactions: list[ParsedTransaction] = []
        for row in csv_rows:
            parsed = parse_csv_transaction(row, mapping)
            if parsed:
                parsed_transactions.append(parsed)
            else:
                console.print(f"[yellow]Skipping invalid row: {row}[/yellow]")

        # Insert parsed transactions
        stats = insert_parsed_transactions(parsed_transactions, db_path, verbose)

        # Display results
        console.print(f"[green]Successfully imported {stats.inserted} transactions![/green]")
        if stats.skipped > 0:
            console.print(f"[dim]Skipped {stats.skipped} duplicates[/dim]")
            if verbose and stats.duplicates:
                render_duplicate_report(stats.duplicates)

        console.print("[dim]Note: During review, use 'i' to ignore payments/transfers (excluded from reports)[/dim]\n")

        save_source = typer.confirm("Save this CSV as a named source for future syncs?", default=True)
        if save_source:
            source_name = typer.prompt("Enter a name for this source")

            new_source = {
                "name": source_name,
                "type": "csv",
                "path": str(csv_path),
                "date_column": mapping["date_column"],
                "description_column": mapping["description_column"],
                "amount_column": mapping["amount_column"],
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
