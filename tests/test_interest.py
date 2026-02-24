# msmed_calculator/tests/test_interest.py
"""
Tests for engine/interest.py — compound interest with monthly rests per MSMED Act Section 16.

Expected values for sample_transactions.csv with interest_rate=19.5%:

  P1: 100,000 | due May-16 | settled Aug-18 → 94 days overdue
      Compound: 3 complete months (May-16→Aug-16) + 2 remaining days
      Interest = 5064.68

  P2: 15,000 | due Jun-20 | settled Oct-19 → 121 days overdue
      Compound: 3 complete months (Jun-20→Sep-20) + 29 remaining days
      Interest = 990.50

  P3: 30,210 | due Sep-14 | settled Oct-19 → 35 days overdue
      Compound: 1 complete month (Sep-14→Oct-14) + 5 remaining days
      Interest = 571.38

  P4a & P4b: Advance → 0 interest

Total V01 interest: 6626.56
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import date

from engine.mapper import generate_settlement_ledger
from engine.interest import calculate_interest, _compound_interest_monthly_rests, _add_months

INTEREST_RATE = 19.5
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_transactions.csv")


def load_fixture_ledger():
    df = pd.read_csv(FIXTURE)
    df["dates"] = pd.to_datetime(df["dates"])
    df["transactions"] = df["transactions"].astype(float)
    ledger = generate_settlement_ledger(df)
    interest_df = calculate_interest(ledger, INTEREST_RATE)
    return interest_df[interest_df["vendor_id"] == "V01"].reset_index(drop=True)


class TestCompoundInterestHelper:
    """Unit tests for the _compound_interest_monthly_rests helper directly."""

    def test_zero_days_returns_zero(self):
        result = _compound_interest_monthly_rests(100000, 19.5, date(2025, 1, 1), date(2025, 1, 1))
        assert result == 0.0

    def test_end_before_start_returns_zero(self):
        result = _compound_interest_monthly_rests(100000, 19.5, date(2025, 6, 1), date(2025, 1, 1))
        assert result == 0.0

    def test_exactly_one_month(self):
        """Exactly 1 complete month: P × (1 + r/12) - P = P × r/12."""
        monthly_rate = 19.5 / 100 / 12
        expected = round(100000 * monthly_rate, 2)
        result = _compound_interest_monthly_rests(100000, 19.5, date(2025, 1, 1), date(2025, 2, 1))
        assert result == pytest.approx(expected, abs=0.01)

    def test_exactly_two_months(self):
        """2 complete months: P × (1 + r/12)^2 - P."""
        monthly_rate = 19.5 / 100 / 12
        expected = round(100000 * ((1 + monthly_rate) ** 2 - 1), 2)
        result = _compound_interest_monthly_rests(100000, 19.5, date(2025, 1, 1), date(2025, 3, 1))
        assert result == pytest.approx(expected, abs=0.01)

    def test_partial_month_only(self):
        """15 days < 1 month: partial month only, slightly less than simple interest."""
        # Partial month only: balance × monthly_rate × (15/31) for January
        result = _compound_interest_monthly_rests(100000, 19.5, date(2025, 1, 1), date(2025, 1, 16))
        monthly_rate = 19.5 / 100 / 12
        expected = round(100000 * monthly_rate * (15 / 31), 2)
        assert result == pytest.approx(expected, abs=0.01)

    def test_compound_higher_than_simple_for_multi_month(self):
        """For multi-month periods, compound interest must exceed simple interest."""
        simple = round(100000 * (19.5 / 100) * (94 / 365), 2)
        compound = _compound_interest_monthly_rests(100000, 19.5, date(2025, 5, 16), date(2025, 8, 18))
        assert compound > simple, f"Compound ({compound}) should exceed simple ({simple})"

    def test_add_months_clamps_to_month_end(self):
        """Jan-31 + 1 month should clamp to Feb-28 (not overflow to Mar-03)."""
        result = _add_months(date(2025, 1, 31), 1)
        assert result == date(2025, 2, 28)


class TestInterestWorkedExample:
    """Assert exact interest figures for the sample fixture."""

    def setup_method(self):
        self.df = load_fixture_ledger()
        self.df = self.df.sort_values(
            ["purchase_date", "payment_date"], na_position="last"
        ).reset_index(drop=True)

    def _find_row(self, purchase_date_str, payment_date_str=None):
        mask = self.df["purchase_date"].astype(str).str.startswith(purchase_date_str)
        if payment_date_str:
            mask &= self.df["payment_date"].astype(str).str.startswith(payment_date_str)
        rows = self.df[mask]
        assert len(rows) >= 1, (
            f"Row not found: purchase={purchase_date_str}, payment={payment_date_str}\n"
            f"Available:\n{self.df[['purchase_date','payment_date','amount_settled','interest_amount']].to_string()}"
        )
        return rows.iloc[0]

    def test_p1_compound_interest(self):
        """100,000 | 94 days | 3 months + 2 days → ₹5,064.68"""
        row = self._find_row("2025-04-01", "2025-08-18")
        assert row["interest_amount"] == pytest.approx(5064.68, abs=0.02)

    def test_p2_compound_interest(self):
        """15,000 | 121 days | 3 months + 29 days → ₹990.50"""
        row = self._find_row("2025-05-06", "2025-10-19")
        assert row["interest_amount"] == pytest.approx(990.50, abs=0.02)

    def test_p3_compound_interest(self):
        """30,210 | 35 days | 1 month + 5 days → ₹571.38"""
        row = self._find_row("2025-07-31", "2025-10-19")
        assert row["interest_amount"] == pytest.approx(571.38, abs=0.02)

    def test_p4a_advance_zero(self):
        row = self._find_row("2025-11-25", "2025-10-19")
        assert row["settlement_type"] == "Advance"
        assert row["interest_amount"] == 0.0

    def test_p4b_advance_zero(self):
        row = self._find_row("2025-11-25", "2025-10-31")
        assert row["settlement_type"] == "Advance"
        assert row["interest_amount"] == 0.0

    def test_total_v01_interest(self):
        """V01 total compound interest = ₹6,626.56"""
        total = self.df["interest_amount"].sum()
        assert total == pytest.approx(6626.56, abs=0.05)

    def test_annual_rate_column_matches_input(self):
        """annual_interest_rate column = exactly what the user typed."""
        assert (self.df["annual_interest_rate"] == INTEREST_RATE).all()

    def test_five_rows_for_v01(self):
        assert len(self.df) == 5


class TestInterestRules:

    def _make_ledger_row(self, purchase_date, payment_date, amount_settled, settlement_type):
        return pd.DataFrame([{
            "vendor_id": "V01",
            "vendor_name": "Test",
            "purchase_index": 0,
            "purchase_date": pd.Timestamp(purchase_date),
            "purchase_amount": -amount_settled,
            "payment_index": 0 if payment_date else None,
            "payment_date": pd.Timestamp(payment_date) if payment_date else None,
            "amount_settled": amount_settled,
            "settlement_type": settlement_type,
        }])

    def test_advance_always_zero_interest(self):
        ledger = self._make_ledger_row("2025-11-25", "2025-10-19", 50000, "Advance")
        result = calculate_interest(ledger, interest_rate=19.5)
        assert result.iloc[0]["days_overdue"] == 0
        assert result.iloc[0]["interest_amount"] == 0.0

    def test_payment_within_45_days_zero_interest(self):
        ledger = self._make_ledger_row("2025-01-01", "2025-01-31", 50000, "Standard")
        result = calculate_interest(ledger, interest_rate=19.5)
        assert result.iloc[0]["days_overdue"] == 0
        assert result.iloc[0]["interest_amount"] == 0.0

    def test_payment_on_due_date_zero_interest(self):
        ledger = self._make_ledger_row("2025-01-01", "2025-02-15", 50000, "Standard")
        result = calculate_interest(ledger, interest_rate=19.5)
        assert result.iloc[0]["days_overdue"] == 0
        assert result.iloc[0]["interest_amount"] == 0.0

    def test_zero_days_overdue_means_zero_interest(self):
        df = load_fixture_ledger()
        assert (df[df["days_overdue"] == 0]["interest_amount"] == 0.0).all()

    def test_compound_is_higher_than_simple_for_long_overdue(self):
        """Compound must exceed simple for multi-month overdue (P1 scenario)."""
        ledger = self._make_ledger_row("2025-04-01", "2025-08-18", 100000, "Standard")
        result = calculate_interest(ledger, interest_rate=19.5)
        compound = result.iloc[0]["interest_amount"]
        simple = round(100000 * (19.5 / 100) * (94 / 365), 2)
        assert compound > simple

    def test_user_rate_applied_directly(self):
        """Custom rate 15% → annual_interest_rate column = 15.0, no multiplier."""
        ledger = self._make_ledger_row("2025-01-01", "2025-06-01", 100000, "Standard")
        result = calculate_interest(ledger, interest_rate=15.0)
        assert result.iloc[0]["annual_interest_rate"] == 15.0

    def test_one_month_compound_formula(self):
        """Exactly one month overdue: interest = P × (r/12)."""
        # Jan-01 purchase → due Feb-15 → settled Mar-15 → 28 days overdue
        # Feb-15 to Mar-15 = 1 complete month
        ledger = self._make_ledger_row("2025-01-01", "2025-03-15", 100000, "Standard")
        result = calculate_interest(ledger, interest_rate=19.5)
        monthly_rate = 19.5 / 100 / 12
        expected = round(100000 * monthly_rate, 2)
        assert result.iloc[0]["interest_amount"] == pytest.approx(expected, abs=0.02)
