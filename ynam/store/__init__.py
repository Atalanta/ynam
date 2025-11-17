"""Database store layer - provides persistence for the application.

This module re-exports all public database functions for easy importing.
"""

# Re-export schema functions
# Re-export all query functions
from ynam.store.queries import (
    add_category,
    auto_categorize_by_description,
    get_all_budgets,
    get_all_categories,
    get_all_transactions,
    get_auto_allocate_rule,
    get_auto_ignore_rule,
    get_budget,
    get_category_breakdown,
    get_monthly_tbb,
    get_most_recent_transaction_date,
    get_suggested_category,
    get_transactions_by_category,
    get_unreviewed_transactions,
    insert_transaction,
    mark_transaction_ignored,
    set_auto_allocate_rule,
    set_auto_ignore_rule,
    set_budget,
    set_monthly_tbb,
    update_transaction_review,
)
from ynam.store.schema import database_exists, get_db_path, init_database

__all__ = [
    # Schema
    "database_exists",
    "get_db_path",
    "init_database",
    # Queries
    "add_category",
    "auto_categorize_by_description",
    "get_all_budgets",
    "get_all_categories",
    "get_all_transactions",
    "get_auto_allocate_rule",
    "get_auto_ignore_rule",
    "get_budget",
    "get_category_breakdown",
    "get_monthly_tbb",
    "get_most_recent_transaction_date",
    "get_suggested_category",
    "get_transactions_by_category",
    "get_unreviewed_transactions",
    "insert_transaction",
    "mark_transaction_ignored",
    "set_auto_allocate_rule",
    "set_auto_ignore_rule",
    "set_budget",
    "set_monthly_tbb",
    "update_transaction_review",
]
