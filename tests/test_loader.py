# msmed_calculator/tests/test_loader.py
"""
Tests for ingestion/loader.py — load_raw_columns().
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from ingestion.loader import load_raw_columns

FIXTURE_CSV = os.path.join(os.path.dirname(__file__), "fixtures", "sample_transactions.csv")
SAMPLE_XLSX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Sample File.xlsx")


class TestLoadRawColumns:

    def test_csv_returns_list(self):
        cols = load_raw_columns(FIXTURE_CSV)
        assert isinstance(cols, list)
        assert len(cols) > 0

    def test_csv_contains_required_columns(self):
        cols = load_raw_columns(FIXTURE_CSV)
        cols_lower = [c.lower() for c in cols]
        assert "vendor_id" in cols_lower
        assert "transactions" in cols_lower
        assert "dates" in cols_lower

    def test_csv_columns_are_strings(self):
        cols = load_raw_columns(FIXTURE_CSV)
        assert all(isinstance(c, str) for c in cols)

    def test_csv_columns_stripped_of_whitespace(self):
        cols = load_raw_columns(FIXTURE_CSV)
        assert all(c == c.strip() for c in cols)

    def test_xlsx_returns_list(self):
        if not os.path.exists(SAMPLE_XLSX):
            pytest.skip("Sample File.xlsx not found — skipping xlsx test.")
        cols = load_raw_columns(SAMPLE_XLSX)
        assert isinstance(cols, list)
        assert len(cols) > 0

    def test_unsupported_extension_raises(self, tmp_path):
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_raw_columns(str(bad_file))
