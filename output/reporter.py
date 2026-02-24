# msmed_calculator/output/reporter.py
"""
Builds human-readable detailed ledger and summary DataFrames.
"""

import pandas as pd
from typing import Optional


def build_detailed_report(interest_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a human-readable version of the interest DataFrame with:
    - Renamed columns for display
    - Sorted by vendor_id, then purchase_date
    - Amounts as floats (formatting is exporter's responsibility)
    """
    if interest_df.empty:
        return pd.DataFrame()

    df = interest_df.copy()

    # Sort for display
    df = df.sort_values(["vendor_id", "purchase_date", "purchase_index", "payment_index"],
                        na_position="last").reset_index(drop=True)

    # Select and rename display columns
    display_cols = {
        "vendor_id": "Vendor ID",
        "vendor_name": "Vendor Name",
        "purchase_date": "Purchase Date",
        "purchase_amount": "Purchase Amount (₹)",
        "payment_date": "Payment Date",
        "amount_settled": "Amount Settled (₹)",
        "settlement_type": "Settlement Type",
        "due_date": "Due Date",
        "days_overdue": "Days Overdue",
        "annual_interest_rate": "Interest Rate (%)",
        "interest_amount": "Interest Amount (₹)",
    }

    # Only keep columns that exist
    cols_to_use = {k: v for k, v in display_cols.items() if k in df.columns}
    df = df[list(cols_to_use.keys())].rename(columns=cols_to_use)

    # Convert purchase_amount to absolute value for display
    if "Purchase Amount (₹)" in df.columns:
        df["Purchase Amount (₹)"] = df["Purchase Amount (₹)"].abs()

    return df


def build_summary_report(interest_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate by vendor_id:
      - total_purchase_amount: sum of all purchase amounts (absolute) per vendor
      - total_payment_amount: sum of all payment amounts per vendor
      - total_interest: sum of interest_amount per vendor
      - count_late_payments: LedgerRows where days_overdue > 0
      - count_on_time_payments: LedgerRows where days_overdue == 0
    """
    if interest_df.empty:
        return pd.DataFrame()

    records = []

    for vendor_id, group in interest_df.groupby("vendor_id"):
        vendor_name = group["vendor_name"].iloc[0] if "vendor_name" in group.columns else str(vendor_id)

        # Total purchases from raw file
        vendor_raw = raw_df[raw_df["vendor_id"].astype(str) == str(vendor_id)]
        total_purchases = vendor_raw.loc[
            vendor_raw["transactions"].astype(float) < 0, "transactions"
        ].astype(float).abs().sum()

        total_payments = vendor_raw.loc[
            vendor_raw["transactions"].astype(float) > 0, "transactions"
        ].astype(float).sum()

        total_interest = round(group["interest_amount"].sum(), 2)
        count_late = int((group["days_overdue"] > 0).sum())
        count_on_time = int((group["days_overdue"] == 0).sum())
        interest_bearing_amount = round(
            group.loc[group["days_overdue"] > 0, "amount_settled"].sum(), 2
        )

        records.append({
            "Vendor ID": vendor_id,
            "Vendor Name": vendor_name,
            "Total Purchases (₹)": round(total_purchases, 2),
            "Total Payments (₹)": round(total_payments, 2),
            "Interest-Bearing Amount (₹)": interest_bearing_amount,
            "Total Interest Due (₹)": total_interest,
            "Late Settlements": count_late,
            "On-Time Settlements": count_on_time,
        })

    return pd.DataFrame(records)
