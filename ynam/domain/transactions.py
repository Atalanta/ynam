"""Pure functions for transaction processing and categorization logic.

This module contains the functional core for transaction operations:
- No I/O operations (no database, no console, no files)
- No side effects
- Pure data transformations
- Easy to test

All monetary amounts are in pence (Money type).
"""

import re
from dataclasses import dataclass
from typing import Any, TypedDict

from ynam.domain.models import CategoryName, Description, Money


class CsvMapping(TypedDict):
    """CSV column mapping configuration."""

    date_column: str
    description_column: str
    amount_column: str


class ParsedTransaction(TypedDict):
    """Parsed transaction data ready for insertion."""

    date: str
    description: str
    amount: int  # in pence


@dataclass(frozen=True)
class Transaction:
    """Immutable transaction data."""

    id: int
    date: str
    description: Description
    amount: Money
    category: CategoryName | None = None
    reviewed: bool = False
    ignored: bool = False


@dataclass(frozen=True)
class TransactionMatch:
    """Immutable transaction matching result."""

    transaction: Transaction
    suggested_category: CategoryName | None
    match_reason: str | None


@dataclass(frozen=True)
class DuplicateCheck:
    """Immutable duplicate check result."""

    is_duplicate: bool
    duplicate_id: int | None


def normalize_description(description: str) -> str:
    """Normalize transaction description for matching.

    Args:
        description: Raw transaction description.

    Returns:
        Normalized description (lowercase, whitespace normalized).
    """
    return " ".join(description.lower().split())


def calculate_similarity_score(desc1: str, desc2: str) -> float:
    """Calculate similarity score between two descriptions.

    Simple word-based similarity using Jaccard coefficient.

    Args:
        desc1: First description.
        desc2: Second description.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    words1 = set(normalize_description(desc1).split())
    words2 = set(normalize_description(desc2).split())

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def find_best_category_match(
    description: str,
    category_samples: dict[CategoryName, list[str]],
    threshold: float = 0.3,
) -> CategoryName | None:
    """Find best category match based on description similarity.

    Args:
        description: Transaction description to match.
        category_samples: Dictionary of category names to sample descriptions.
        threshold: Minimum similarity threshold (0.0-1.0).

    Returns:
        Best matching category name or None if no match above threshold.
    """
    best_score = 0.0
    best_category: CategoryName | None = None

    for category, samples in category_samples.items():
        for sample in samples:
            score = calculate_similarity_score(description, sample)
            if score > best_score:
                best_score = score
                best_category = category

    if best_score >= threshold:
        return best_category
    return None


def matches_ignore_pattern(description: str, pattern: str) -> bool:
    """Check if description matches ignore pattern.

    Args:
        description: Transaction description.
        pattern: Ignore pattern (can be substring or regex).

    Returns:
        True if description matches pattern.
    """
    normalized_desc = normalize_description(description)
    normalized_pattern = normalize_description(pattern)

    # Simple substring match
    if normalized_pattern in normalized_desc:
        return True

    # Try regex match
    try:
        if re.search(normalized_pattern, normalized_desc, re.IGNORECASE):
            return True
    except re.error:
        pass

    return False


def matches_allocate_pattern(description: str, pattern: str) -> bool:
    """Check if description matches auto-allocate pattern.

    Args:
        description: Transaction description.
        pattern: Auto-allocate pattern (can be substring or regex).

    Returns:
        True if description matches pattern.
    """
    return matches_ignore_pattern(description, pattern)


def format_money_display(amount: Money, include_sign: bool = True) -> str:
    """Format money amount for display.

    Args:
        amount: Amount in pence.
        include_sign: Whether to include + or - sign.

    Returns:
        Formatted string (e.g., "-£123.45" or "£123.45").
    """
    pounds = abs(amount) / 100
    formatted = f"£{pounds:,.2f}"

    if include_sign:
        if amount < 0:
            return f"-{formatted}"
        else:
            return f"+{formatted}"
    else:
        return formatted


def is_duplicate_transaction(
    date: str,
    description: str,
    amount: Money,
    existing_transactions: list[tuple[int, str, str, Money]],
) -> DuplicateCheck:
    """Check if transaction is a duplicate.

    Args:
        date: Transaction date (YYYY-MM-DD).
        description: Transaction description.
        amount: Transaction amount in pence.
        existing_transactions: List of (id, date, description, amount) tuples.

    Returns:
        DuplicateCheck with result.
    """
    for txn_id, existing_date, existing_desc, existing_amount in existing_transactions:
        if existing_date == date and existing_desc == description and existing_amount == amount:
            return DuplicateCheck(is_duplicate=True, duplicate_id=txn_id)

    return DuplicateCheck(is_duplicate=False, duplicate_id=None)


def categorize_transaction_auto(
    transaction: Transaction,
    ignore_rules: dict[str, str],
    allocate_rules: dict[str, CategoryName],
    category_samples: dict[CategoryName, list[str]],
) -> TransactionMatch:
    """Automatically categorize transaction based on rules and similarity.

    Args:
        transaction: Transaction to categorize.
        ignore_rules: Dictionary of ignore patterns.
        allocate_rules: Dictionary of pattern -> category mappings.
        category_samples: Dictionary of category -> sample descriptions.

    Returns:
        TransactionMatch with suggested category and reason.
    """
    description = str(transaction.description)

    # Check ignore rules
    for pattern in ignore_rules.values():
        if matches_ignore_pattern(description, pattern):
            return TransactionMatch(
                transaction=transaction,
                suggested_category=None,
                match_reason="matches_ignore_rule",
            )

    # Check auto-allocate rules
    for pattern, category in allocate_rules.items():
        if matches_allocate_pattern(description, pattern):
            return TransactionMatch(
                transaction=transaction,
                suggested_category=category,
                match_reason="matches_allocate_rule",
            )

    # Try similarity matching
    suggested = find_best_category_match(description, category_samples)
    if suggested:
        return TransactionMatch(
            transaction=transaction,
            suggested_category=suggested,
            match_reason="similarity_match",
        )

    return TransactionMatch(
        transaction=transaction,
        suggested_category=None,
        match_reason=None,
    )


def parse_api_transaction(raw_txn: dict[str, Any]) -> tuple[str, str, Money]:
    """Parse transaction from Starling API format.

    Args:
        raw_txn: Raw transaction dictionary from API.

    Returns:
        Tuple of (date, description, amount).
    """
    date = raw_txn["transactionTime"][:10]
    description = raw_txn.get("counterPartyName", "Unknown")
    amount = int(raw_txn["amount"]["minorUnits"])

    if raw_txn.get("direction") == "OUT":
        amount = -amount

    return date, description, Money(amount)


def parse_csv_row(
    row: dict[str, str],
    date_col: str,
    desc_col: str,
    amount_col: str,
    negate: bool = False,
) -> tuple[str, str, Money]:
    """Parse transaction from CSV row.

    Args:
        row: CSV row as dictionary.
        date_col: Column name for date.
        desc_col: Column name for description.
        amount_col: Column name for amount.
        negate: Whether to negate the amount.

    Returns:
        Tuple of (date, description, amount).
    """
    date = row[date_col].strip()
    description = row[desc_col].strip()
    amount_str = row[amount_col].strip().replace("£", "").replace(",", "")
    amount_pounds = float(amount_str)
    amount_pence = int(amount_pounds * 100)

    if negate:
        amount_pence = -amount_pence

    return date, description, Money(amount_pence)


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


def parse_csv_transaction(row: dict[str, str], mapping: CsvMapping) -> ParsedTransaction | None:
    """Parse a CSV row into a transaction using the provided mapping.

    Args:
        row: CSV row as dictionary.
        mapping: Column mapping configuration.

    Returns:
        ParsedTransaction if valid, None if row should be skipped.
    """
    # Extract and validate date
    raw_date = row.get(mapping["date_column"], "").strip()
    if not raw_date:
        return None
    date = raw_date[:10]

    # Extract description (default to "Unknown" if missing)
    description = row.get(mapping["description_column"], "").strip() or "Unknown"

    # Extract and validate amount
    raw_amount = row.get(mapping["amount_column"], "").strip()
    if not raw_amount:
        return None

    try:
        amount = int(float(raw_amount) * 100)
    except ValueError:
        return None

    # CSV imports are expenses (negative amounts)
    amount = -abs(amount)

    return ParsedTransaction(date=date, description=description, amount=amount)
