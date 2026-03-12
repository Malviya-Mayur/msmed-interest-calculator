# msmed_calculator/tests/test_mapper.py
"""
Tests for engine/mapper.py — FIFO settlement ledger generation.
Run from msmed_calculator/ directory:  pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import datetime

from engine.mapper import generate_settlement_ledger


def make_df(transactions, dates, vendor_ids=None, vendor_names=None):
    """Helper to build a minimal test DataFrame."""
    n = len(transactions)
    data = {
        "transactions": [float(t) for t in transactions],
        "dates": pd.to_datetime(dates),
        "vendor_id": vendor_ids if vendor_ids else ["V01"] * n,
        "vendor_name": vendor_names if vendor_names else ["Test Vendor"] * n,
    }
    return pd.DataFrame(data)


class TestFIFOSettlement:

    def test_single_purchase_single_payment_produces_one_row(self):
        """One purchase + one payment → one LedgerRow."""
        df = make_df(
            transactions=[-10000, 10000],
            dates=["2025-01-01", "2025-02-01"],
        )
        ledger = generate_settlement_ledger(df)
        assert len(ledger) == 1
        assert ledger.iloc[0]["settlement_type"] == "Standard"
        assert ledger.iloc[0]["amount_settled"] == 10000.0

    def test_three_purchases_two_payments_correct_row_count(self):
        """
        3 purchases (10k, 5k, 8k = 23k total) + 2 payments (15k, 8k = 23k).
        Payment 1 (15k): covers Purchase 1 (10k) → one row, then partial Purchase 2 (5k) → one row.
        Payment 2 (8k):  covers remaining Purchase 2 (0, already done) → Purchase 3 (8k) → one row.
        Total: 3 LedgerRows.
        """
        df = make_df(
            transactions=[-10000, -5000, -8000, 15000, 8000],
            dates=["2025-01-01", "2025-02-01", "2025-03-01", "2025-06-01", "2025-07-01"],
        )
        ledger = generate_settlement_ledger(df)
        # P1 fully settled by pay1, P2 fully settled by pay1 (partial), P3 by pay2
        assert len(ledger) == 3

    def test_partial_settlement_produces_multiple_rows_for_one_purchase(self):
        """
        One purchase of 20k, settled by payment 1 (12k) and payment 2 (8k):
        → 2 LedgerRows for the same purchase_index.
        """
        df = make_df(
            transactions=[-20000, 12000, 8000],
            dates=["2025-01-01", "2025-06-01", "2025-07-01"],
        )
        ledger = generate_settlement_ledger(df)
        assert len(ledger) == 2
        # Both rows should refer to same purchase
        assert ledger.iloc[0]["purchase_amount"] == -20000.0
        assert ledger.iloc[1]["purchase_amount"] == -20000.0
        assert round(ledger.iloc[0]["amount_settled"] + ledger.iloc[1]["amount_settled"], 2) == 20000.0

    def test_advance_payment_identified_correctly(self):
        """
        Payment (inflow date) BEFORE purchase (outflow date) → settlement_type == 'Advance'.
        One 50k payment for a 65k purchase: 50k advance + 15k unsettled = 2 rows.
        """
        df = make_df(
            transactions=[50000, -65000],
            dates=["2025-10-19", "2025-11-25"],
        )
        ledger = generate_settlement_ledger(df)
        # 50k covered by advance, remaining 15k unsettled
        assert len(ledger) == 2
        advance_rows = ledger[ledger["settlement_type"] == "Advance"]
        assert len(advance_rows) == 1
        assert advance_rows.iloc[0]["amount_settled"] == 50000.0

    def test_standard_payment_identified_when_payment_after_purchase(self):
        """
        Payment after purchase → settlement_type == 'Standard'.
        """
        df = make_df(
            transactions=[-100000, 100000],
            dates=["2025-04-01", "2025-08-18"],
        )
        ledger = generate_settlement_ledger(df)
        assert len(ledger) == 1
        assert ledger.iloc[0]["settlement_type"] == "Standard"

    def test_unsettled_purchase_appears_in_ledger(self):
        """
        A purchase with no corresponding payment → Unsettled row in ledger.
        """
        df = make_df(
            transactions=[-10000, -5000, 5000],
            dates=["2025-01-01", "2025-02-01", "2025-06-01"],
        )
        ledger = generate_settlement_ledger(df)
        unsettled = ledger[ledger["settlement_type"] == "Unsettled"]
        assert len(unsettled) >= 1
        # Unsettled row has no payment_date
        assert unsettled.iloc[0]["payment_date"] is None or pd.isna(unsettled.iloc[0]["payment_date"])

    def test_vendors_never_mixed(self):
        """
        Two vendors: V01 and V02.
        V01: purchase 10k, payment 10k
        V02: purchase 8k, payment 8k
        Each vendor should have exactly 1 LedgerRow using only their own transactions.
        """
        df = make_df(
            transactions=[-10000, 10000, -8000, 8000],
            dates=["2025-01-01", "2025-06-01", "2025-02-01", "2025-07-01"],
            vendor_ids=["V01", "V01", "V02", "V02"],
            vendor_names=["Vendor A", "Vendor A", "Vendor B", "Vendor B"],
        )
        ledger = generate_settlement_ledger(df)
        assert len(ledger) == 2
        v01_rows = ledger[ledger["vendor_id"] == "V01"]
        v02_rows = ledger[ledger["vendor_id"] == "V02"]
        assert len(v01_rows) == 1
        assert len(v02_rows) == 1
        assert v01_rows.iloc[0]["amount_settled"] == 10000.0
        assert v02_rows.iloc[0]["amount_settled"] == 8000.0

    def test_sample_fixture_produces_five_rows(self):
        """
        Full sample from Section 4 of the plan: correct FIFO allocation produces
        5 LedgerRows for V01 (purchases P1→Pay1, P2→Pay2, P3→Pay2, P4→Pay2+Pay3).
        """
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_transactions.csv")
        df = pd.read_csv(fixture_path)
        df["dates"] = pd.to_datetime(df["dates"])
        df["transactions"] = df["transactions"].astype(float)

        ledger = generate_settlement_ledger(df)
        v01 = ledger[ledger["vendor_id"] == "V01"]
        assert len(v01) == 5


class TestFIFODateOrdering:
    """
    Regression tests ensuring that the FIFO settlement always uses DATE order,
    not row/file order — regardless of how the input rows are arranged.
    """

    def test_purchase_settled_by_future_payment_not_past_payment(self):
        """
        The key regression test for the date-ordering bug.

        Timeline:
          Jan 1  → Purchase 10k  (P1)
          Mar 1  → Payment  15k  (Pay1) — settles P1 fully (10k), leaving 5k surplus
          Jun 1  → Purchase 10k  (P2)   — gets 5k from Pay1 surplus (Advance),
                                          then 5k from Pay2 (Standard)
          Aug 1  → Payment  10k  (Pay2) — used to settle P2 remainder

        Key assertion: the old bug caused Pay1 (Mar 1) to consume ALL 15k for P1
        (which was only 10k — but the pooling was correct). The important test is
        that Pay2 (Aug 1) is correctly used for P2, not just left as unsettled.
        """
        df = make_df(
            transactions=[15000, -10000, 10000, -10000],
            dates=["2025-03-01", "2025-01-01", "2025-08-01", "2025-06-01"],
        )
        ledger = generate_settlement_ledger(df)

        # P1 (Jan 1) must be fully settled (10k) by Pay1 (Mar 1)
        p1 = ledger[ledger["purchase_date"] == pd.Timestamp("2025-01-01").date()]
        assert p1["amount_settled"].sum() == 10000.0
        assert all(p1["payment_date"] == pd.Timestamp("2025-03-01").date())
        assert all(p1["settlement_type"] == "Standard")

        # P2 (Jun 1) must be fully settled (10k total); some from Pay1 remainder,
        # some from Pay2. No "Unsettled" rows.
        p2 = ledger[ledger["purchase_date"] == pd.Timestamp("2025-06-01").date()]
        assert p2["amount_settled"].sum() == 10000.0
        assert "Unsettled" not in p2["settlement_type"].values
        # Pay2 (Aug 1) must be used for P2 — at least one row must reference Aug 1
        assert pd.Timestamp("2025-08-01").date() in p2["payment_date"].values

    def test_standard_settlement_type_requires_payment_after_purchase(self):
        """
        All Standard rows must have payment_date > purchase_date.
        All Advance rows must have payment_date < purchase_date.
        """
        df = make_df(
            transactions=[-100000, -15000, -30210, 100000, -65000, 80000, 50000],
            dates=["2025-04-01", "2025-05-06", "2025-07-31",
                   "2025-08-18", "2025-11-25", "2025-10-19", "2025-10-31"],
        )
        ledger = generate_settlement_ledger(df)

        standard_rows = ledger[ledger["settlement_type"] == "Standard"]
        for _, row in standard_rows.iterrows():
            assert row["payment_date"] > row["purchase_date"], (
                f"Standard row has payment_date {row['payment_date']} "
                f"<= purchase_date {row['purchase_date']}"
            )

        advance_rows = ledger[ledger["settlement_type"] == "Advance"]
        for _, row in advance_rows.iterrows():
            assert row["payment_date"] < row["purchase_date"], (
                f"Advance row has payment_date {row['payment_date']} "
                f">= purchase_date {row['purchase_date']}"
            )

    def test_out_of_order_rows_produce_same_result_as_sorted_rows(self):
        """
        Giving the engine rows in random order should produce the same
        settlement result as giving them in date order.
        """
        sorted_df = make_df(
            transactions=[-10000, -5000, 10000, 5000],
            dates=["2025-01-01", "2025-02-01", "2025-06-01", "2025-07-01"],
        )
        scrambled_df = make_df(
            transactions=[10000, -5000, 5000, -10000],
            dates=["2025-06-01", "2025-02-01", "2025-07-01", "2025-01-01"],
        )

        ledger_sorted = generate_settlement_ledger(sorted_df)
        ledger_scrambled = generate_settlement_ledger(scrambled_df)

        # Both should produce the same number of rows
        assert len(ledger_sorted) == len(ledger_scrambled)

        # Total amount settled should match
        assert round(ledger_sorted["amount_settled"].sum(), 2) == \
               round(ledger_scrambled["amount_settled"].sum(), 2)
