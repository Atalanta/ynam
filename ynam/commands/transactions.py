"""Transaction management commands (add, comment, delete)."""

import sys

import pandas as pd
import typer
from rich.console import Console

from ynam.domain.models import CategoryName, Money
from ynam.store.queries import (
    add_category,
    get_all_categories,
    insert_transaction,
    update_transaction_category,
    update_transaction_comment,
)
from ynam.store.schema import get_db_path

console = Console()


def add_command(
    date: str,
    description: str,
    amount: float,
    category: str | None = None,
    source: str | None = None,
) -> None:
    """Add a transaction manually.

    Args:
        date: Transaction date (YYYY-MM-DD, DD/MM/YYYY, or other formats).
        description: Transaction description.
        amount: Transaction amount in pounds (negative for expenses, positive for income).
        category: Optional category name.
        source: Optional source name (e.g., 'manual', 'cash').
    """
    db_path = get_db_path()

    try:
        # Normalize date using pandas
        normalized_date = pd.to_datetime(date, dayfirst=True).strftime("%Y-%m-%d")
    except Exception as e:
        console.print(f"[red]Invalid date format: {e}[/red]")
        console.print("[dim]Accepted formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, etc.[/dim]")
        sys.exit(1)

    # Convert amount to pence
    amount_pence = Money(int(amount * 100))

    # Use 'manual' as default source
    source = source or "manual"

    try:
        # Insert transaction
        inserted, duplicate_id = insert_transaction(
            normalized_date,
            description,
            amount_pence,
            db_path,
            source=source,
        )

        if not inserted:
            console.print(f"[yellow]Transaction already exists (ID: {duplicate_id})[/yellow]")
            sys.exit(0)

        console.print("[green]✓[/green] Transaction added:")
        console.print(f"  Date: {normalized_date}")
        console.print(f"  Description: {description}")
        console.print(f"  Amount: £{amount:.2f}")
        console.print(f"  Source: {source}")

        # If category provided, categorize it
        if category:
            # Check if category exists
            categories = get_all_categories(db_path)
            category_name = CategoryName(category)

            if category_name not in categories:
                console.print(f"\n[yellow]Category '{category}' doesn't exist yet[/yellow]")
                create_cat = typer.confirm("Create it?", default=True)
                if create_cat:
                    add_category(category_name, db_path)
                    console.print(f"[green]✓[/green] Created category: {category}")
                else:
                    console.print("[dim]Transaction added without category (use 'ynam review' to categorize)[/dim]")
                    return

            # Categorize the transaction
            update_transaction_category(normalized_date, description, amount_pence, source, category_name, db_path)

            console.print(f"[green]✓[/green] Categorized as: {category}")
        else:
            console.print("[dim]Transaction added (use 'ynam review' to categorize)[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def comment_command(
    transaction_id: int,
    comment: str,
) -> None:
    """Add or update a comment on a transaction.

    Args:
        transaction_id: Transaction ID (from 'ynam list' or 'ynam inspect').
        comment: Comment text.
    """
    db_path = get_db_path()

    try:
        # Get transaction to verify it exists and get details for display
        from ynam.store.queries import get_all_transactions

        transactions = get_all_transactions(db_path, limit=None)
        txn = next((t for t in transactions if t["id"] == transaction_id), None)

        if not txn:
            console.print(f"[red]Transaction {transaction_id} not found[/red]")
            sys.exit(1)

        date = txn["date"]
        description = txn["description"]
        amount = txn["amount"]
        old_comment = txn.get("comment")

        # Update comment
        update_transaction_comment(transaction_id, comment, db_path)

        console.print(f"[green]✓[/green] Updated comment for transaction {transaction_id}:")
        console.print(f"  Date: {date}")
        console.print(f"  Description: {description}")

        if amount < 0:
            amount_display = f"-£{abs(amount) / 100:.2f}"
        else:
            amount_display = f"+£{amount / 100:.2f}"
        console.print(f"  Amount: {amount_display}")

        if old_comment:
            console.print(f"  [dim]Old comment: {old_comment}[/dim]")
        console.print(f"  [yellow]New comment: {comment}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
