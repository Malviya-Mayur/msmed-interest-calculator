# msmed_calculator/tests/test_validator.py
"""
Tests for ingestion/validator.py — schema validation and coercion.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

from ingestion.validator import validate, ValidationError, ValidationResult


def make_valid_df():
    """A minimal, fully-valid DataFrame."""
    return pd.DataFrame({
        "transaction_id": ["T1", "T2"],
        "vendor_id": ["V01", "V01"],
        "vendor_name": ["Test Vendor", "Test Vendor"],
        "transactions": ["-10000", "10000"],
        "dates": ["2025-01-01", "2025-06-01"],
    })


class TestValidatorSchemaChecks:

    def test_valid_df_passes(self):
        result = validate(make_valid_df())
        assert result.is_valid is True
        assert len(result.clean_df) == 2
        assert not result.errors or len(result.errors) == 0

    def test_missing_transactions_column_raises_validation_error(self):
        df = make_valid_df().drop(columns=["transactions"])
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        assert "transactions" in str(exc_info.value).lower()

    def test_missing_dates_column_raises_validation_error(self):
        df = make_valid_df().drop(columns=["dates"])
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        assert "dates" in str(exc_info.value).lower()

    def test_missing_vendor_id_column_raises_validation_error(self):
        df = make_valid_df().drop(columns=["vendor_id"])
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        assert "vendor_id" in str(exc_info.value).lower()

    def test_missing_multiple_columns_lists_all(self):
        df = make_valid_df().drop(columns=["transactions", "dates"])
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        msg = str(exc_info.value).lower()
        assert "transactions" in msg or "dates" in msg


class TestValidatorCoercion:

    def test_zero_amount_rows_are_dropped_silently(self):
        df = make_valid_df()
        df.loc[len(df)] = {
            "transaction_id": "T_ZERO",
            "vendor_id": "V01",
            "vendor_name": "Test Vendor",
            "transactions": "0",
            "dates": "2025-03-01",
        }
        result = validate(df)
        # The zero row should be dropped, leaving 2 valid rows
        assert len(result.clean_df) == 2

    def test_zero_rows_generate_error_notice(self):
        df = make_valid_df()
        df.loc[len(df)] = {
            "transaction_id": "T_ZERO",
            "vendor_id": "V01",
            "vendor_name": "Test Vendor",
            "transactions": "0",
            "dates": "2025-03-01",
        }
        result = validate(df)
        # An error notice should be in the errors list
        assert any("zero" in e.lower() for e in result.errors)

    def test_non_numeric_transaction_dropped_with_notice(self):
        df = make_valid_df()
        df.loc[len(df)] = {
            "transaction_id": "T_BAD",
            "vendor_id": "V01",
            "vendor_name": "Test Vendor",
            "transactions": "NOT_A_NUMBER",
            "dates": "2025-03-01",
        }
        result = validate(df)
        assert len(result.clean_df) == 2  # Bad row dropped
        assert any("non-numeric" in e.lower() for e in result.errors)

    def test_unparseable_date_generates_error(self):
        df = make_valid_df()
        df.loc[len(df)] = {
            "transaction_id": "T_BADDATE",
            "vendor_id": "V01",
            "vendor_name": "Test Vendor",
            "transactions": "-5000",
            "dates": "NOT-A-DATE",
        }
        result = validate(df)
        # The bad-date row should be dropped
        assert len(result.clean_df) == 2
        assert any("date" in e.lower() for e in result.errors)

    def test_transactions_coerced_to_float(self):
        result = validate(make_valid_df())
        assert result.clean_df["transactions"].dtype == float

    def test_dates_coerced_to_datetime(self):
        result = validate(make_valid_df())
        assert pd.api.types.is_datetime64_any_dtype(result.clean_df["dates"])


class TestValidatorBusinessRules:

    def test_no_inflow_raises_validation_error(self):
        df = pd.DataFrame({
            "vendor_id": ["V01"],
            "vendor_name": ["Test"],
            "transactions": ["-10000"],
            "dates": ["2025-01-01"],
        })
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        assert "inflow" in str(exc_info.value).lower() or "payment" in str(exc_info.value).lower()

    def test_no_outflow_raises_validation_error(self):
        df = pd.DataFrame({
            "vendor_id": ["V01"],
            "vendor_name": ["Test"],
            "transactions": ["10000"],
            "dates": ["2025-01-01"],
        })
        with pytest.raises(ValidationError) as exc_info:
            validate(df)
        assert "outflow" in str(exc_info.value).lower() or "purchase" in str(exc_info.value).lower()

    def test_empty_after_cleaning_raises_validation_error(self):
        df = pd.DataFrame({
            "vendor_id": ["V01", "V01"],
            "vendor_name": ["Test", "Test"],
            "transactions": ["NOT_VALID", "0"],
            "dates": ["2025-01-01", "2025-02-01"],
        })
        with pytest.raises(ValidationError):
            validate(df)

    def test_sample_fixture_passes_validation(self):
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "sample_transactions.csv")
        df = pd.read_csv(fixture, dtype=str)
        result = validate(df)
        assert result.is_valid is True
        assert len(result.clean_df) == 7
