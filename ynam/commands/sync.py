"""Sync command for importing transactions."""

import csv
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import typer
from rich.console import Console
from rich.table import Table

from ynam.config import add_source, get_config_path, get_source, load_config
from ynam.domain.models import Money
from ynam.domain.transactions import CsvMapping, ParsedTransaction, analyze_csv_columns, parse_csv_transaction
from ynam.integrations.starling import get_account_info, get_transactions
from ynam.store.queries import get_most_recent_transaction_date, insert_transaction
from ynam.store.schema import get_db_path, get_sources_dir

console = Console()


def normalize_csv_date(raw_date: str) -> str:
    """Normalize a CSV date string to ISO format (YYYY-MM-DD).

    Uses pandas.to_datetime for robust date parsing - handles ISO, European,
    American, and various other date formats automatically. Bank exports are
    notoriously inconsistent, so we need fuzzy matching.

    Args:
        raw_date: Raw date string from CSV.

    Returns:
        Normalized date in YYYY-MM-DD format.

    Raises:
        ValueError: If date cannot be parsed.
    """
    try:
        # pandas.to_datetime handles ISO, European, American, and many other formats
        parsed_date = pd.to_datetime(raw_date, dayfirst=True)
        return parsed_date.strftime("%Y-%m-%d")
    except (ValueError, pd.errors.ParserError) as e:
        raise ValueError(f"Could not parse date '{raw_date}': {e}") from e


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
    # Check if it's a direct CSV file path
    csv_path = Path(source_name_or_path).expanduser()
    if csv_path.exists() and csv_path.suffix.lower() == ".csv":
        return csv_path, None

    # Check if it's a source directory in XDG sources/
    source_dir = get_sources_dir() / source_name_or_path
    if source_dir.exists() and source_dir.is_dir():
        # Check for CSV files in directory
        csv_files = list(source_dir.glob("*.csv"))
        if csv_files:
            # Return directory-based source with implicit config
            return None, {
                "name": source_name_or_path,
                "type": "csv-dir",
                "directory": source_dir,
            }

    # Check config for named source
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

        # Also check for source directories
        sources_dir = get_sources_dir()
        if sources_dir.exists():
            dir_sources = [d.name for d in sources_dir.iterdir() if d.is_dir()]
            if dir_sources:
                console.print("\n[yellow]Available directory sources:[/yellow]")
                for dir_name in dir_sources:
                    console.print(f"  • {dir_name} (csv-dir)")

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


def prompt_for_csv_source_name(csv_sources: list[dict[str, Any]]) -> tuple[str, bool]:
    """Prompt user to identify CSV source or create new one.

    Args:
        csv_sources: List of CSV source configurations from config.

    Returns:
        Tuple of (source_name, should_save_to_config).
    """
    if csv_sources:
        console.print(f"\n[cyan]I see you have {len(csv_sources)} CSV source(s) configured:[/cyan]")
        for idx, src in enumerate(csv_sources, 1):
            console.print(f"  {idx}. {src['name']}")

        console.print(f"  {len(csv_sources) + 1}. New source")

        choice_str: str = typer.prompt(f"\nIs this one of these, or a new source? [1-{len(csv_sources) + 1}]", type=str)

        try:
            choice = int(choice_str)
            if 1 <= choice <= len(csv_sources):
                selected_source = csv_sources[choice - 1]["name"]
                console.print(f"[green]Using source: {selected_source}[/green]")
                return selected_source, False
        except ValueError:
            pass

    # New source flow
    console.print("\n[yellow]You have no named CSV sources configured.[/yellow]")
    source_name = typer.prompt("Enter source name to tag these transactions", type=str)

    # Confirmation with user's exact input
    confirm = typer.confirm(
        f'To be clear: transactions from this import will be tagged as "{source_name}"',
        default=True,
    )

    if not confirm:
        console.print("[red]Aborted[/red]")
        sys.exit(0)

    # Ask about saving to config
    save_to_config = typer.confirm(
        "Are you likely to import from this source again? If so, I recommend adding\n"
        "this to your config so you'll get this option next time.\n\n"
        f'Save "{source_name}" to config?',
        default=True,
    )

    if not save_to_config:
        console.print(f'[dim]Okay, transactions will be tagged as "{source_name}" but not saved to config.[/dim]')

    return source_name, save_to_config


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


def insert_parsed_transactions(
    transactions: list[ParsedTransaction], db_path: Path, verbose: bool, source: str, backfill_source: bool = False
) -> ImportStats:
    """Insert parsed transactions into database.

    Args:
        transactions: List of parsed transactions to insert.
        db_path: Path to database.
        verbose: Whether to track duplicates for reporting.
        source: Source name to tag transactions with.

    Returns:
        ImportStats with insertion results.
    """
    inserted = 0
    skipped = 0
    duplicates: list[dict[str, Any]] = []

    for txn in transactions:
        success, duplicate_id = insert_transaction(
            txn["date"], txn["description"], Money(txn["amount"]), db_path, source, backfill_source
        )
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
    backfill_source: bool = False,
) -> None:
    """Sync transactions from a configured source or CSV file path."""
    db_path = get_db_path()

    csv_path, source = resolve_sync_source(source_name_or_path)

    if csv_path:
        sync_new_csv_file(csv_path, db_path, verbose, backfill_source)
        return

    assert source is not None, "source must be set if csv_path is None"
    source_type = source.get("type")

    if source_type == "api":
        sync_api_source(source, db_path, days, verbose, backfill_source)
    elif source_type == "csv":
        sync_csv_source(source, db_path, verbose, backfill_source)
    elif source_type == "csv-dir":
        sync_csv_dir_source(source, db_path, verbose, backfill_source)
    else:
        console.print(f"[red]Unknown source type: {source_type}[/red]", style="bold")
        sys.exit(1)


def sync_api_source(
    source: dict[str, Any],
    db_path: Path,
    days_override: int | None = None,
    verbose: bool = False,
    backfill_source: bool = False,
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

        source_name = source.get("name", "unknown")

        for txn in transactions:
            date = txn["transactionTime"][:10]
            description = txn.get("counterPartyName", "Unknown")
            amount = int(txn["amount"]["minorUnits"])

            if txn.get("direction") == "OUT":
                amount = -amount

            success, duplicate_id = insert_transaction(
                date, description, Money(amount), db_path, source_name, backfill_source
            )
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


def sync_csv_dir_source(
    source: dict[str, Any], db_path: Path, verbose: bool = False, backfill_source: bool = False
) -> None:
    """Sync transactions from all CSV files in a directory source.

    Args:
        source: Source configuration dict with 'directory' key.
        db_path: Path to database.
        verbose: Show detailed duplicate report.
        backfill_source: Update source on duplicates with NULL source.
    """
    source_dir = source.get("directory")
    if not source_dir:
        console.print("[red]No directory specified for csv-dir source[/red]", style="bold")
        sys.exit(1)

    source_name = source.get("name", "unknown")

    # Find all CSV files in directory
    csv_files = sorted(source_dir.glob("*.csv"))
    if not csv_files:
        console.print(f"[yellow]No CSV files found in {source_dir}[/yellow]")
        return

    console.print(f"[cyan]Found {len(csv_files)} CSV file(s) in {source_dir}[/cyan]")

    # Load or prompt for column mapping
    try:
        config_source = get_source(source_name)
    except FileNotFoundError:
        config_source = None

    date_col = config_source.get("date_column") if config_source else None
    desc_col = config_source.get("description_column") if config_source else None
    amount_col = config_source.get("amount_column") if config_source else None

    # If no mapping, analyze first CSV and prompt
    if not all([date_col, desc_col, amount_col]):
        console.print("[yellow]No column mapping configured. Analyzing first CSV...[/yellow]\n")

        with open(csv_files[0], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            sample_rows = list(reader)

        if not sample_rows:
            console.print("[red]First CSV is empty, cannot configure[/red]", style="bold")
            sys.exit(1)

        headers = list(sample_rows[0].keys())
        suggested = analyze_csv_columns(headers)

        console.print("\n[bold cyan]Sample row from first CSV:[/bold cyan]")
        for key, value in list(sample_rows[0].items())[:5]:
            console.print(f"  {key}: {value}")
        console.print()

        mapping = prompt_for_csv_mapping(headers, suggested)

        date_col = mapping["date_column"]
        desc_col = mapping["description_column"]
        amount_col = mapping["amount_column"]

        # Save to config
        new_source = {
            "name": source_name,
            "type": "csv-dir",
            "date_column": date_col,
            "description_column": desc_col,
            "amount_column": amount_col,
        }
        add_source(new_source)
        console.print("\n[green]✓[/green] Source configuration saved")

    # At this point, we're guaranteed to have valid column names
    assert date_col and desc_col and amount_col, "Column names must be set"

    # Create mapping for parsing
    mapping = CsvMapping(date_column=date_col, description_column=desc_col, amount_column=amount_col)

    # Process all CSV files
    total_inserted = 0
    total_skipped = 0
    all_duplicates: list[dict[str, Any]] = []

    for csv_file in csv_files:
        console.print(f"\n[cyan]Processing {csv_file.name}...[/cyan]")

        try:
            with open(csv_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                csv_rows = list(reader)

            if not csv_rows:
                console.print(f"[yellow]  No transactions in {csv_file.name}[/yellow]")
                continue

            # Parse transactions
            parsed_transactions: list[ParsedTransaction] = []
            parse_errors = 0
            for row_num, row in enumerate(csv_rows, start=2):  # start=2 because row 1 is header
                try:
                    parsed = parse_csv_transaction(row, mapping, normalize_csv_date)
                    if parsed:
                        parsed_transactions.append(parsed)
                except ValueError as e:
                    parse_errors += 1
                    console.print(f"[yellow]  Row {row_num}: {e}[/yellow]")
                    continue

            if parse_errors > 0:
                console.print(f"[yellow]  Skipped {parse_errors} rows with date parsing errors[/yellow]")

            # Insert transactions
            stats = insert_parsed_transactions(parsed_transactions, db_path, verbose, source_name, backfill_source)

            total_inserted += stats.inserted
            total_skipped += stats.skipped
            all_duplicates.extend(stats.duplicates)

            total_processed = stats.inserted + stats.skipped
            console.print(
                f"[green]  Processed {total_processed}, imported {stats.inserted}, skipped {stats.skipped} duplicates[/green]"
            )

        except Exception as e:
            console.print(f"[red]  Error processing {csv_file.name}: {e}[/red]")
            continue

    # Display summary
    console.print(f"\n[green]Successfully imported {total_inserted} transactions![/green]", style="bold")
    if total_skipped > 0:
        console.print(f"[dim]Skipped {total_skipped} duplicates across all files[/dim]")
        if verbose and all_duplicates:
            render_duplicate_report(all_duplicates)

    console.print("[dim]Note: During review, use 'i' to ignore payments/transfers (excluded from reports)[/dim]")


def sync_csv_source(
    source: dict[str, Any], db_path: Path, verbose: bool = False, backfill_source: bool = False
) -> None:
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
        parse_errors = 0
        for row_num, row in enumerate(csv_rows, start=2):  # start=2 because row 1 is header
            try:
                parsed = parse_csv_transaction(row, mapping, normalize_csv_date)
                if parsed:
                    parsed_transactions.append(parsed)
            except ValueError as e:
                parse_errors += 1
                console.print(f"[yellow]Row {row_num}: {e}[/yellow]")
                continue

        if parse_errors > 0:
            console.print(f"[yellow]Skipped {parse_errors} rows with date parsing errors[/yellow]")

        # Insert parsed transactions with source name
        source_name = source.get("name", "unknown")
        stats = insert_parsed_transactions(parsed_transactions, db_path, verbose, source_name, backfill_source)

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


def sync_new_csv_file(csv_path: Path, db_path: Path, verbose: bool = False, backfill_source: bool = False) -> None:
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

        # Prompt for source name
        config = load_config()
        csv_sources = [s for s in config.get("sources", []) if s.get("type") == "csv"]
        source_name, should_save = prompt_for_csv_source_name(csv_sources)

        # Parse transactions using domain function
        console.print(f"\n[cyan]Importing {len(csv_rows)} transactions as expenses...[/cyan]")
        parsed_transactions: list[ParsedTransaction] = []
        parse_errors = 0
        for row_num, row in enumerate(csv_rows, start=2):  # start=2 because row 1 is header
            try:
                parsed = parse_csv_transaction(row, mapping, normalize_csv_date)
                if parsed:
                    parsed_transactions.append(parsed)
            except ValueError as e:
                parse_errors += 1
                console.print(f"[yellow]Row {row_num}: {e}[/yellow]")
                continue

        if parse_errors > 0:
            console.print(f"[yellow]Skipped {parse_errors} rows with date parsing errors[/yellow]")

        # Insert parsed transactions with source name
        stats = insert_parsed_transactions(parsed_transactions, db_path, verbose, source_name, backfill_source)

        # Display results
        console.print(f"[green]Successfully imported {stats.inserted} transactions![/green]")
        if stats.skipped > 0:
            console.print(f"[dim]Skipped {stats.skipped} duplicates[/dim]")
            if verbose and stats.duplicates:
                render_duplicate_report(stats.duplicates)

        console.print("[dim]Note: During review, use 'i' to ignore payments/transfers (excluded from reports)[/dim]\n")

        # Save to config if user requested
        if should_save:
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
