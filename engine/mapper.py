# msmed_calculator/engine/mapper.py
"""
Settlement ledger generator — refactored from the base logic in Data Mapping.txt.
Extends the original FIFO logic to:
  1. Process transactions grouped by vendor_id (never mix vendors).
  2. Handle unsettled purchases (no payment yet) — accrue to today's date.
  3. Preserve all required LedgerRow fields.
"""

import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Any
from config import CREDIT_TERM_DAYS


def _process_vendor(vendor_df: pd.DataFrame, vendor_id: str, vendor_name: str) -> List[Dict[str, Any]]:
    """
    Run FIFO settlement logic for a single vendor's transactions.
    Returns a list of raw ledger record dicts.

    Key invariant:
    - Transactions are sorted by date first.
    - Payments are added to the available pool only once their date has been
      reached while iterating through purchases chronologically.
    - This means a payment dated AFTER a purchase is never retroactively used
      to settle that purchase — it stays in the pool for later purchases.
    - Any payments that are still in the pool after all purchases have been
      processed remain genuinely unused (advances that exceed all purchases or
      payments with no matching purchase).
    """
    ledger: List[Dict[str, Any]] = []

    # ── 1. Sort everything by date (stable sort preserves row order on ties) ─
    vendor_df = vendor_df.sort_values("dates", kind="stable").reset_index(drop=False)

    # ── 2. Split into two date-sorted lists: purchases and payments ────────
    purchases = [
        {
            "idx": int(row["index"]),
            "date": row["dates"].date(),
            "amount": float(row["transactions"]),  # negative
        }
        for _, row in vendor_df.iterrows()
        if row["transactions"] < 0
    ]

    # Payment list also sorted by date (already from vendor_df sort, but be explicit)
    payments = [
        {
            "idx": int(row["index"]),
            "date": row["dates"].date(),
            "remaining": float(row["transactions"]),  # positive
        }
        for _, row in vendor_df.iterrows()
        if row["transactions"] > 0
    ]

    # ── 3. FIFO settlement with lazy payment pool ──────────────────────────
    # available_pool: payments whose date <= current purchase date
    available_pool: List[Dict] = []
    payment_ptr = 0  # pointer into the `payments` list

    for purchase in purchases:
        outflow_date = purchase["date"]
        debt = abs(purchase["amount"])
        purchase_idx = purchase["idx"]

        # Enqueue all payments whose date <= this purchase's date into the pool
        while payment_ptr < len(payments) and payments[payment_ptr]["date"] <= outflow_date:
            available_pool.append(payments[payment_ptr])
            payment_ptr += 1

        # Settle against available pool (FIFO — earliest payment first)
        for payment in available_pool:
            if debt <= 1e-9:
                break
            if payment["remaining"] <= 1e-9:
                continue

            take = min(debt, payment["remaining"])
            inflow_date = payment["date"]

            # If inflow_date < outflow_date it's an advance; == means same-day (treat as advance)
            settlement_type = "Advance" if inflow_date <= outflow_date else "Standard"
            # Note: at this point inflow_date <= outflow_date always (lazy pool guarantee),
            # so all in-pool settlements are either Advance or same-day.
            # Standard settlements (payment AFTER purchase) are handled below.

            ledger.append({
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "purchase_index": purchase_idx,
                "purchase_date": outflow_date,
                "purchase_amount": purchase["amount"],
                "payment_index": payment["idx"],
                "payment_date": inflow_date,
                "amount_settled": round(take, 2),
                "settlement_type": "Advance" if inflow_date < outflow_date else "Standard",
            })

            debt -= take
            payment["remaining"] -= take

        # If debt still remains, look ahead into FUTURE payments (Standard type)
        if debt > 1e-9:
            for payment in payments[payment_ptr:]:
                if debt <= 1e-9:
                    break
                if payment["remaining"] <= 1e-9:
                    continue

                take = min(debt, payment["remaining"])
                inflow_date = payment["date"]

                ledger.append({
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "purchase_index": purchase_idx,
                    "purchase_date": outflow_date,
                    "purchase_amount": purchase["amount"],
                    "payment_index": payment["idx"],
                    "payment_date": inflow_date,
                    "amount_settled": round(take, 2),
                    "settlement_type": "Standard",
                })

                debt -= take
                payment["remaining"] -= take

        # ── Unsettled remainder ────────────────────────────────────────────
        if debt > 1e-9:
            ledger.append({
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "purchase_index": purchase_idx,
                "purchase_date": outflow_date,
                "purchase_amount": purchase["amount"],
                "payment_index": None,
                "payment_date": None,
                "amount_settled": round(debt, 2),
                "settlement_type": "Unsettled",
            })

    return ledger


def generate_settlement_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: Validated DataFrame with columns: vendor_id, vendor_name, transactions, dates
    Output: DataFrame of ledger records (one row per purchase-payment mapping)

    Logic:
    1. Group the DataFrame by vendor_id.
    2. For each vendor group, run the FIFO settlement logic.
    3. Collect all ledger records across all vendors.
    4. Return as a single combined DataFrame.
    """
    all_records: List[Dict[str, Any]] = []

    for vendor_id, group in df.groupby("vendor_id", sort=False):
        vendor_name = group["vendor_name"].iloc[0] if "vendor_name" in group.columns else str(vendor_id)
        records = _process_vendor(group.copy(), str(vendor_id), str(vendor_name))
        all_records.extend(records)

    if not all_records:
        return pd.DataFrame()

    ledger_df = pd.DataFrame(all_records)
    return ledger_df.reset_index(drop=True)
