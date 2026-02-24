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
    """
    ledger: List[Dict[str, Any]] = []

    # Sort everything chronologically
    vendor_df = vendor_df.sort_values("dates").reset_index(drop=False)
    # 'index' column now holds the original df index (useful for purchase_index/payment_index)

    # ── Build available inflows list (payments, transactions > 0) ──────────
    available_inflows = []
    for _, row in vendor_df.iterrows():
        if row["transactions"] > 0:
            available_inflows.append({
                "inflow_idx": int(row["index"]),
                "inflow_date": row["dates"].date(),
                "remaining": float(row["transactions"]),
            })

    # ── Process each outflow (purchase, transactions < 0) in FIFO order ───
    for _, row in vendor_df.iterrows():
        amount = row["transactions"]
        if amount >= 0:
            continue  # skip payments

        debt = abs(float(amount))
        outflow_date: date = row["dates"].date()
        purchase_idx = int(row["index"])

        settled_any = False

        for inflow in available_inflows:
            if debt <= 1e-9:
                break
            if inflow["remaining"] <= 1e-9:
                continue

            take = min(debt, inflow["remaining"])
            inflow_date: date = inflow["inflow_date"]

            settlement_type = "Advance" if inflow_date < outflow_date else "Standard"

            ledger.append({
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "purchase_index": purchase_idx,
                "purchase_date": outflow_date,
                "purchase_amount": float(amount),
                "payment_index": inflow["inflow_idx"],
                "payment_date": inflow_date,
                "amount_settled": round(take, 2),
                "settlement_type": settlement_type,
            })

            debt -= take
            inflow["remaining"] -= take
            settled_any = True

        # ── Unsettled remainder (no more inflows) ──────────────────────────
        if debt > 1e-9:
            ledger.append({
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "purchase_index": purchase_idx,
                "purchase_date": outflow_date,
                "purchase_amount": float(amount),
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
