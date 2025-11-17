"""Review command for categorizing transactions."""

import sqlite3
import sys
from pathlib import Path
from typing import Any

import typer
from rich.columns import Columns
from rich.console import Console

from ynam.domain.models import CategoryName
from ynam.store.queries import (
    add_category,
    get_all_categories,
    get_auto_allocate_rule,
    get_auto_ignore_rule,
    get_suggested_category,
    get_unreviewed_transactions,
    mark_transaction_ignored,
    set_auto_allocate_rule,
    set_auto_ignore_rule,
    update_transaction_review,
)
from ynam.store.schema import get_db_path

console = Console()


def display_transaction_details(txn: dict[str, Any]) -> None:
    """Display transaction details for review.

    Args:
        txn: Transaction dictionary.
    """
    amount = txn["amount"]
    if amount < 0:
        amount_display = f"-£{abs(amount) / 100:.2f}"
    else:
        amount_display = f"+£{amount / 100:.2f}"

    console.print(f"[bold]Date:[/bold] {txn['date']}")
    console.print(f"[bold]Description:[/bold] {txn['description']}")
    console.print(f"[bold]Amount:[/bold] {amount_display}\n")


def prompt_category_choice(categories: list[CategoryName], suggested: CategoryName | None) -> str:
    """Display categories and prompt for user choice.

    Args:
        categories: List of available categories.
        suggested: Optional suggested category.

    Returns:
        User's choice as string.
    """
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
            result: str = typer.prompt(prompt_text, type=str, default="")
            return result
        else:
            prompt_text = f"\nSelect category (1-{len(categories)}, n for new, s to skip, i to ignore, q to quit)"
            result2: str = typer.prompt(prompt_text, type=str)
            return result2
    else:
        console.print("[dim]No categories yet[/dim]")
        result3: str = typer.prompt("\nEnter category name (or s to skip, i to ignore, q to quit)", type=str)
        return result3


def handle_special_choice(
    choice: str, txn: dict[str, Any], suggested: CategoryName | None, db_path: Path
) -> tuple[bool, bool]:
    """Handle special choices (q, s, i, a).

    Args:
        choice: User's choice.
        txn: Transaction dictionary.
        suggested: Optional suggested category.
        db_path: Path to database.

    Returns:
        Tuple of (should_continue, was_processed).
        - should_continue: False means quit/skip, True means continue processing
        - was_processed: True means transaction was handled (categorized or ignored)
    """
    if choice.lower() == "q":
        console.print("[yellow]Exiting[/yellow]")
        return False, False

    if choice.lower() == "s":
        console.print("[dim]Skipped[/dim]\n")
        return False, False

    if choice.lower() == "i":
        mark_transaction_ignored(txn["id"], db_path)
        auto_ignore = typer.confirm("Always ignore transactions like this?", default=False)
        if auto_ignore:
            set_auto_ignore_rule(txn["description"], db_path)
            console.print("[dim]Ignored (will auto-ignore similar transactions)[/dim]\n")
        else:
            console.print("[dim]Ignored (excluded from reports)[/dim]\n")
        return False, True

    if choice.lower() == "a" and suggested:
        set_auto_allocate_rule(txn["description"], suggested, db_path)
        update_transaction_review(txn["id"], suggested, db_path)
        console.print(f"[green]Auto-allocating as: {suggested}[/green]\n")
        return False, True

    return True, False


def resolve_category_selection(
    choice: str, categories: list[CategoryName], suggested: CategoryName | None, db_path: Path
) -> CategoryName | None:
    """Resolve user's category selection.

    Args:
        choice: User's choice string.
        categories: List of available categories.
        suggested: Optional suggested category.
        db_path: Path to database.

    Returns:
        Selected category name, or None if invalid.
    """
    if not categories:
        new_cat = CategoryName(choice)
        add_category(new_cat, db_path)
        console.print(f"[green]Added new category: {choice}[/green]")
        return new_cat

    if choice == "" and suggested:
        return suggested

    if choice.lower() == "n":
        new_category_str: str = typer.prompt("Enter new category name", type=str)
        new_cat = CategoryName(new_category_str)
        add_category(new_cat, db_path)
        console.print(f"[green]Added new category: {new_category_str}[/green]")
        return new_cat

    try:
        choice_idx = int(choice) - 1
        if 0 <= choice_idx < len(categories):
            return categories[choice_idx]
        else:
            console.print("[red]Invalid choice, skipping[/red]\n")
            return None
    except ValueError:
        console.print("[red]Invalid input, skipping[/red]\n")
        return None


def categorize_transaction(txn: dict[str, Any], db_path: Path) -> bool:
    """Categorize a single transaction.

    Args:
        txn: Transaction dictionary.
        db_path: Path to database.

    Returns:
        True if transaction was categorized or ignored, False if skipped or quit.
    """
    display_transaction_details(txn)

    categories = get_all_categories(db_path)
    suggested = get_suggested_category(txn["description"], db_path)

    choice = prompt_category_choice(categories, suggested)

    should_continue, was_processed = handle_special_choice(choice, txn, suggested, db_path)
    if not should_continue:
        return was_processed

    selected_category = resolve_category_selection(choice, categories, suggested, db_path)
    if selected_category is None:
        return False

    update_transaction_review(txn["id"], selected_category, db_path)
    console.print(f"[green]Categorized as: {selected_category}[/green]\n")
    return True


def review_command() -> None:
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
