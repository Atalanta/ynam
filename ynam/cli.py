"""CLI entry point for ynam."""

import typer

from ynam.commands.admin import backup_command, init_command, list_command
from ynam.commands.budget import budget_command
from ynam.commands.report import inspect_command, report_command
from ynam.commands.review import review_command
from ynam.commands.sync import sync_command

app = typer.Typer(
    name="ynam",
    help="You Need A Mirror - A YNAB-inspired money management tool",
    add_completion=False,
)


@app.callback()
def main() -> None:
    """You Need A Mirror - A YNAB-inspired money management tool."""
    pass


@app.command(name="backup")
def backup(
    output_dir: str = typer.Option(None, "--output", "-o", help="Backup directory (default: ~/.ynam/backups)"),
) -> None:
    """Backup your database and configuration files."""
    backup_command(output_dir)


@app.command(name="init")
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing database and config"),
) -> None:
    """Initialize ynam database and configuration."""
    init_command(force)


@app.command()
def sync(
    source_name_or_path: str,
    days: int = typer.Option(None, "--days", help="Days to fetch (overrides config)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed duplicate report"),
) -> None:
    """Sync your transactions from a configured source or CSV file."""
    sync_command(source_name_or_path, days, verbose)


@app.command(name="list")
def list_transactions(
    limit: int = typer.Option(50, help="Maximum transactions to show"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all your transactions"),
) -> None:
    """List your transactions."""
    list_command(limit, all)


@app.command()
def review(
    oldest_first: bool = typer.Option(
        False, "--oldest-first", help="Review oldest transactions first (default: newest first)"
    ),
) -> None:
    """Review and categorize unreviewed transactions."""
    review_command(oldest_first)


@app.command()
def inspect(
    category: str,
    all: bool = typer.Option(False, "--all", "-a", help="Show all time"),
    month: str = typer.Option(None, "--month", help="Specific month (YYYY-MM)"),
) -> None:
    """Inspect your transactions for a specific category."""
    inspect_command(category, all, month)


@app.command(name="report")
def report(
    sort_by: str = typer.Option("value", help="Sort by 'value' or 'alpha'"),
    histogram: bool = typer.Option(True, help="Show histogram of your spending"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all time"),
    month: str = typer.Option(None, "--month", help="Specific month (YYYY-MM)"),
) -> None:
    """Show your income and spending breakdown."""
    report_command(sort_by, histogram, all, month)


@app.command()
def budget(
    set_tbb: float = typer.Option(None, "--set-tbb", help="Set your To Be Budgeted amount for the month (in £)"),
    status: bool = typer.Option(False, "--status", help="Show your budget status and spending"),
    adjust: bool = typer.Option(False, "--adjust", help="Adjust your budget allocations interactively"),
    copy_from: str = typer.Option(
        None, "--copy-from", help="Copy budget from month (YYYY-MM), rolling over unspent amounts"
    ),
    from_cat: str = typer.Option(None, "--from", help="Source category (name, index, or 'TBB')"),
    to_cat: str = typer.Option(None, "--to", help="Target category (name, index, or 'TBB')"),
    amount: float = typer.Option(None, "--amount", help="Amount to transfer (in £)"),
    month: str = typer.Option(None, "--month", help="Month to budget for (YYYY-MM)"),
) -> None:
    """Set your budget amounts for categories."""
    budget_command(set_tbb, status, adjust, copy_from, from_cat, to_cat, amount, month)


if __name__ == "__main__":
    app()
