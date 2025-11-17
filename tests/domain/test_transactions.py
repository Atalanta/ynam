"""Tests for ynam.domain.transactions pure functions."""

from ynam.domain.transactions import (
    CsvMapping,
    analyze_csv_columns,
    parse_csv_transaction,
)


class TestAnalyzeCsvColumns:
    """Tests for analyze_csv_columns."""

    def test_detects_standard_columns(self) -> None:
        """Should detect standard date, description, amount columns."""
        headers = ["Date", "Description", "Amount"]
        result = analyze_csv_columns(headers)

        assert result["date"] == "Date"
        assert result["description"] == "Description"
        assert result["amount"] == "Amount"

    def test_case_insensitive_detection(self) -> None:
        """Should detect columns regardless of case."""
        headers = ["DATE", "DESCRIPTION", "AMOUNT"]
        result = analyze_csv_columns(headers)

        assert result["date"] == "DATE"
        assert result["description"] == "DESCRIPTION"
        assert result["amount"] == "AMOUNT"

    def test_detects_merchant_name_as_description(self) -> None:
        """Should prefer 'merchant name' for description."""
        headers = ["Date", "Merchant Name", "Amount"]
        result = analyze_csv_columns(headers)

        assert result["description"] == "Merchant Name"

    def test_ignores_currency_amount_columns(self) -> None:
        """Should ignore columns with 'currency' in the name."""
        headers = ["Date", "Description", "Amount", "Amount Currency"]
        result = analyze_csv_columns(headers)

        assert result["amount"] == "Amount"

    def test_returns_empty_for_missing_columns(self) -> None:
        """Should return empty strings for undetected columns."""
        headers = ["Column1", "Column2", "Column3"]
        result = analyze_csv_columns(headers)

        assert result["date"] == ""
        assert result["description"] == ""
        assert result["amount"] == ""

    def test_uses_first_match_only(self) -> None:
        """Should use first matching column."""
        headers = ["Transaction Date", "Date", "Description"]
        result = analyze_csv_columns(headers)

        # Should pick first column with "date"
        assert result["date"] == "Transaction Date"


class TestParseCsvTransaction:
    """Tests for parse_csv_transaction."""

    def test_parses_valid_row(self) -> None:
        """Should parse valid CSV row."""
        row = {"Date": "2025-01-15", "Description": "Coffee Shop", "Amount": "4.50"}
        mapping = CsvMapping(
            date_column="Date",
            description_column="Description",
            amount_column="Amount",
        )

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["date"] == "2025-01-15"
        assert result["description"] == "Coffee Shop"
        assert result["amount"] == -450  # £4.50 in pence, negative for expense

    def test_truncates_long_date(self) -> None:
        """Should truncate date to YYYY-MM-DD."""
        row = {
            "Date": "2025-01-15T10:30:00Z",
            "Description": "Test",
            "Amount": "10.00",
        }
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["date"] == "2025-01-15"

    def test_handles_missing_description(self) -> None:
        """Should use 'Unknown' for missing description."""
        row = {"Date": "2025-01-15", "Description": "", "Amount": "5.00"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["description"] == "Unknown"

    def test_returns_none_for_missing_date(self) -> None:
        """Should return None if date is missing."""
        row = {"Date": "", "Description": "Test", "Amount": "5.00"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is None

    def test_returns_none_for_missing_amount(self) -> None:
        """Should return None if amount is missing."""
        row = {"Date": "2025-01-15", "Description": "Test", "Amount": ""}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is None

    def test_returns_none_for_invalid_amount(self) -> None:
        """Should return None if amount is not numeric."""
        row = {"Date": "2025-01-15", "Description": "Test", "Amount": "invalid"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is None

    def test_converts_amount_to_pence(self) -> None:
        """Should convert pounds to pence correctly."""
        row = {"Date": "2025-01-15", "Description": "Test", "Amount": "123.45"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["amount"] == -12345  # £123.45 in pence

    def test_makes_amount_negative(self) -> None:
        """Should make all CSV imports negative (expenses)."""
        row = {"Date": "2025-01-15", "Description": "Test", "Amount": "50.00"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["amount"] == -5000  # Negative expense

    def test_handles_already_negative_amount(self) -> None:
        """Should handle amounts that are already negative."""
        row = {"Date": "2025-01-15", "Description": "Test", "Amount": "-50.00"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["amount"] == -5000  # Still negative

    def test_strips_whitespace(self) -> None:
        """Should strip whitespace from fields."""
        row = {
            "Date": "  2025-01-15  ",
            "Description": "  Coffee Shop  ",
            "Amount": "  4.50  ",
        }
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is not None
        assert result["date"] == "2025-01-15"
        assert result["description"] == "Coffee Shop"
        assert result["amount"] == -450

    def test_handles_missing_columns_in_row(self) -> None:
        """Should return None if mapped columns don't exist in row."""
        row = {"WrongColumn": "value"}
        mapping = CsvMapping(date_column="Date", description_column="Description", amount_column="Amount")

        result = parse_csv_transaction(row, mapping)

        assert result is None
