"""Admin commands for backup, init, and listing transactions."""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ynam.config import create_default_config, get_config_path
from ynam.store.queries import get_all_transactions
from ynam.store.schema import get_db_path, init_database

console = Console()


def backup_command(
    output_dir: str | None = None,
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


def run_migration(db_path: Path) -> None:
    """Run database migrations on existing database."""
    console.print(f"[cyan]Running migrations on {db_path}...[/cyan]")
    init_database(db_path)
    console.print("[green]✓[/green] Migrations complete")
    console.print("[dim]Database schema is up to date[/dim]")


def run_full_init(db_path: Path, config_path: Path) -> None:
    """Initialize new database and config."""
    console.print(f"[cyan]Initializing database at {db_path}...[/cyan]")
    init_database(db_path)
    console.print("[green]✓[/green] Database initialized")

    console.print(f"[cyan]Creating config file at {config_path}...[/cyan]")
    create_default_config(config_path)
    console.print("[green]✓[/green] Config file created (permissions: 600)")

    console.print("\n[green]Initialization complete![/green]", style="bold")
    console.print(f"[dim]Database: {db_path}[/dim]")
    console.print(f"[dim]Config: {config_path}[/dim]")


def init_command(force: bool = False, migrate: bool = False) -> None:
    """Initialize ynam database and configuration."""
    db_path = get_db_path()
    config_path = get_config_path()

    db_exists = db_path.exists()
    config_exists = config_path.exists()

    try:
        # Migration path: update existing database only
        if migrate:
            if not db_exists:
                console.print("[red]No database found to migrate[/red]", style="bold")
                console.print(f"[dim]Expected location: {db_path}[/dim]")
                sys.exit(1)
            run_migration(db_path)
            return

        # Guard: refuse to overwrite without force flag
        if not force and (db_exists or config_exists):
            console.print("[red]Initialization failed:[/red]", style="bold")
            if db_exists:
                console.print(f"  Database already exists: {db_path}")
            if config_exists:
                console.print(f"  Config already exists: {config_path}")
            console.print("\n[yellow]Use 'ynam init --force' to overwrite[/yellow]")
            console.print("[yellow]Or 'ynam init --migrate' to update database schema only[/yellow]")
            sys.exit(1)

        # Full initialization path
        run_full_init(db_path, config_path)

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
    except OSError as e:
        console.print(f"[red]Filesystem error: {e}[/red]", style="bold")
        sys.exit(1)


def list_command(
    limit: int = 50,
    all: bool = False,
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
        table.add_column("Source", style="dim")
        table.add_column("Status", justify="center")

        for txn in transactions:
            amount = txn["amount"]
            if amount < 0:
                amount_display = f"[red]-£{abs(amount) / 100:,.2f}[/red]"
            else:
                amount_display = f"[green]+£{amount / 100:,.2f}[/green]"

            category = txn.get("category") or "[dim]-[/dim]"
            source = txn.get("source") or "[dim]-[/dim]"

            if txn.get("ignored"):
                status = "⊗"
            elif txn["reviewed"]:
                status = "✓"
            else:
                status = "○"

            table.add_row(txn["date"], txn["description"], amount_display, category, source, status)

        console.print(table)

    except sqlite3.Error as e:
        console.print(f"[red]Database error: {e}[/red]", style="bold")
        sys.exit(1)
