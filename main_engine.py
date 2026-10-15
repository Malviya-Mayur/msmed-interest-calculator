"""
msmed_core_engine.py
====================
Standalone MSME Act Interest & Late-Payment Calculator.

Public API
----------
    generate_settlement_ledger(df)           -> pd.DataFrame
    calculate_interest(ledger_df, rate, ...) -> pd.DataFrame
    summarise_by_vendor(result_df)           -> pd.DataFrame

Data contract (input DataFrame columns)
----------------------------------------
    Required:
        vendor_id       : str   — unique supplier identifier
        transactions    : float — negative = purchase/outflow, positive = payment/inflow
        dates           : date-parseable — transaction date

    Optional:
        vendor_name     : str   — display name (falls back to vendor_id)
        transaction_id  : str   — pass-through, not used in calculation
        narration       : str   — pass-through, not used in calculation

Usage example
-------------
    import pandas as pd
    from msmed_core_engine import generate_settlement_ledger, calculate_interest

    df = pd.read_excel("transactions.xlsx")
    # ... map your column names to vendor_id / transactions / dates ...

    ledger = generate_settlement_ledger(df)
    result = calculate_interest(ledger, interest_rate=19.5)
    print(result)
"""

# ─────────────────────────────────────────────────────────────────────────────
# Standard-library / third-party imports only (no project-local imports)
# ─────────────────────────────────────────────────────────────────────────────
import calendar
import pandas as pd
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Constants  (mirrors config.py)
# ─────────────────────────────────────────────────────────────────────────────

CREDIT_TERM_DAYS: int = 45           # Statutory credit term per MSMED Act
DEFAULT_INTEREST_RATE: float = 19.5  # Default annual rate in % (user can override)
INTEREST_MULTIPLIER: int = 3         # Reference: MSMED Act rate = 3 x bank rate


# ─────────────────────────────────────────────────────────────────────────────
# Data models  (mirrors engine/models.py)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LedgerRow:
    """One purchase-to-payment mapping row in the settlement ledger."""
    vendor_id: str
    vendor_name: str
    purchase_index: int
    purchase_date: date
    purchase_amount: float          # Always negative
    payment_index: Optional[int]
    payment_date: Optional[date]
    amount_settled: float           # Always positive
    settlement_type: str            # 'Advance' | 'Standard' | 'Unsettled'
    due_date: date                  # purchase_date + CREDIT_TERM_DAYS
    days_overdue: int               # max(0, effective_payment_date - due_date)
    interest_bearing_amount: float
    annual_interest_rate: float     # e.g. 19.5
    interest_amount: float


@dataclass
class SummaryRow:
    """Aggregated totals per vendor."""
    vendor_id: str
    vendor_name: str
    total_purchases: float
    total_payments: float
    total_settled_on_time: float
    total_settled_late: float
    total_interest: float


# ─────────────────────────────────────────────────────────────────────────────
# Settlement ledger (FIFO mapper)  — mirrors engine/mapper.py
# ─────────────────────────────────────────────────────────────────────────────

def _process_vendor(
    vendor_df: pd.DataFrame,
    vendor_id: str,
    vendor_name: str,
) -> List[Dict[str, Any]]:
    """
    Run FIFO settlement logic for a single vendor's transactions.

    Key invariant:
    - Transactions are sorted by date first.
    - Payments are added to the available pool only once their date has been
      reached while iterating through purchases chronologically.
    - This means a payment dated AFTER a purchase is never retroactively used
      to settle that purchase -- it stays in the pool for later purchases.
    - Any payments that are still in the pool after all purchases have been
      processed remain genuinely unused (advances that exceed all purchases or
      payments with no matching purchase).

    Returns:
        A list of raw ledger record dicts.
    """
    ledger: List[Dict[str, Any]] = []

    # 1. Sort everything by date (stable sort preserves row order on ties)
    vendor_df = vendor_df.sort_values("dates", kind="stable").reset_index(drop=False)

    # 2. Split into date-sorted lists: purchases (negative) and payments (positive)
    purchases = [
        {
            "idx": int(row["index"]),
            "date": row["dates"].date() if hasattr(row["dates"], "date") else row["dates"],
            "amount": float(row["transactions"]),  # negative
        }
        for _, row in vendor_df.iterrows()
        if row["transactions"] < 0
    ]

    payments = [
        {
            "idx": int(row["index"]),
            "date": row["dates"].date() if hasattr(row["dates"], "date") else row["dates"],
            "remaining": float(row["transactions"]),  # positive
        }
        for _, row in vendor_df.iterrows()
        if row["transactions"] > 0
    ]

    # 3. FIFO settlement with lazy payment pool
    #    available_pool: payments whose date <= current purchase date
    available_pool: List[Dict] = []
    payment_ptr = 0  # pointer into the `payments` list

    for purchase in purchases:
        outflow_date = purchase["date"]
        debt = abs(purchase["amount"])
        purchase_idx = purchase["idx"]

        # Enqueue all payments whose date <= this purchase's date into the pool
        while (
            payment_ptr < len(payments)
            and payments[payment_ptr]["date"] <= outflow_date
        ):
            available_pool.append(payments[payment_ptr])
            payment_ptr += 1

        # Settle against available pool (FIFO -- earliest payment first)
        for payment in available_pool:
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
                # Advance = payment arrived before the purchase date
                "settlement_type": "Advance" if inflow_date < outflow_date else "Standard",
            })

            debt -= take
            payment["remaining"] -= take

        # Debt still remains -- look ahead into FUTURE payments (Standard type)
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

        # Unsettled remainder (no payment found at all)
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
    Generate a FIFO-based settlement ledger from raw transaction data.

    Input DataFrame columns
    -----------------------
        Required : vendor_id, transactions (negative=purchase, positive=payment), dates
        Optional : vendor_name, transaction_id, narration

    Returns
    -------
        pd.DataFrame with columns:
            vendor_id, vendor_name, purchase_index, purchase_date, purchase_amount,
            payment_index, payment_date, amount_settled, settlement_type

        settlement_type values:
            'Advance'   -- payment arrived before the purchase date
            'Standard'  -- payment arrived after the purchase date
            'Unsettled' -- no payment found; interest accrues to today
    """
    if df.empty:
        return pd.DataFrame()

    all_records: List[Dict[str, Any]] = []

    for vendor_id, group in df.groupby("vendor_id", sort=False):
        vendor_name = (
            group["vendor_name"].iloc[0]
            if "vendor_name" in group.columns
            else str(vendor_id)
        )
        records = _process_vendor(group.copy(), str(vendor_id), str(vendor_name))
        all_records.extend(records)

    if not all_records:
        return pd.DataFrame()

    ledger_df = pd.DataFrame(all_records)
    return ledger_df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Interest engine  -- mirrors engine/interest.py
# ─────────────────────────────────────────────────────────────────────────────

def _add_months(d: date, n: int) -> date:
    """Add *n* calendar months to *d*, clamping the day if the target month is shorter."""
    m = d.month + n
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    max_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, max_day))


def _compound_interest_monthly_rests(
    principal: float,
    annual_rate_pct: float,
    interest_start: date,
    interest_end: date,
) -> float:
    """
    Compound interest with monthly rests per MSMED Act Section 16.

    The Act mandates:
        "the buyer shall be liable to pay compound interest with monthly rests
         to the supplier on that amount from the appointed day..."

    Algorithm:
        1. monthly_rate = annual_rate / 12
        2. For each complete calendar month overdue, compound the balance.
        3. For remaining partial-month days, apply simple interest on the
           compounded balance proportional to days / days_in_that_month.

    Args:
        principal         : Amount on which interest is charged (positive float).
        annual_rate_pct   : Annual interest rate as a percentage (e.g. 19.5).
        interest_start    : Date from which interest starts accruing (the due date).
        interest_end      : Date on which interest stops (payment date / today).

    Returns:
        Interest amount rounded to 2 decimal places.
    """
    if interest_end <= interest_start:
        return 0.0

    monthly_rate = annual_rate_pct / 100 / 12

    # Step 1: Count complete calendar months
    complete_months = 0
    boundary = interest_start
    while True:
        next_boundary = _add_months(interest_start, complete_months + 1)
        if next_boundary <= interest_end:
            complete_months += 1
            boundary = next_boundary
        else:
            break

    # Step 2: Compound balance after complete months
    balance = principal * ((1 + monthly_rate) ** complete_months)

    # Step 3: Simple interest on remainder (partial month)
    remaining_days = (interest_end - boundary).days
    if remaining_days > 0:
        days_in_month = calendar.monthrange(boundary.year, boundary.month)[1]
        balance += balance * monthly_rate * (remaining_days / days_in_month)

    return round(balance - principal, 2)


def calculate_interest(
    ledger_df: pd.DataFrame,
    interest_rate: float = DEFAULT_INTEREST_RATE,
    credit_term_days: int = CREDIT_TERM_DAYS,
    interest_method: str = "compound",
) -> pd.DataFrame:
    """
    Enrich the settlement ledger with interest and late-payment flag columns.

    Args:
        ledger_df        : Settlement ledger from generate_settlement_ledger().
        interest_rate    : Annual interest rate in % (default 19.5).
        credit_term_days : Credit period in days (default 45 per MSMED Act).
        interest_method  : 'compound' -- monthly rests (MSMED Act default)
                           'simple'   -- flat daily accrual (P x r x t, t=days/365)

    Returns:
        DataFrame with all original columns PLUS:
            due_date                -- purchase_date + credit_term_days
            days_overdue            -- calendar days past due (0 if on time / advance)
            annual_interest_rate    -- the rate used (stored for audit trail)
            interest_method         -- 'compound' or 'simple'
            interest_bearing_amount -- amount on which interest was charged
            interest_amount         -- calculated interest in currency units
            is_late_payment         -- bool flag: True when days_overdue > 0

    Settlement-type rules:
        Advance   -> days_overdue = 0, interest = 0  (payment before purchase)
        Standard  -> interest accrues from due_date to payment_date
        Unsettled -> interest accrues from due_date to today's date
    """
    if ledger_df.empty:
        return ledger_df

    df = ledger_df.copy()
    today = date.today()

    due_dates: List[date] = []
    days_overdue_list: List[int] = []
    interest_amounts: List[float] = []

    for _, row in df.iterrows():
        purchase_date = row["purchase_date"]
        if isinstance(purchase_date, pd.Timestamp):
            purchase_date = purchase_date.date()

        settlement_type: str = row["settlement_type"]
        amount_settled: float = float(row["amount_settled"])

        # 1. Due date
        due_date = purchase_date + timedelta(days=credit_term_days)

        # 2. Effective payment date
        if settlement_type == "Advance":
            # Advances are never overdue -- force effective date = due_date
            effective_payment_date = due_date
        elif settlement_type == "Unsettled":
            # No payment received yet -- accrue to today
            effective_payment_date = today
        else:
            payment_date = row["payment_date"]
            if isinstance(payment_date, pd.Timestamp):
                payment_date = payment_date.date()
            effective_payment_date = payment_date

        # 3. Days overdue
        days_overdue = max(0, (effective_payment_date - due_date).days)

        # Hard guard: Advances are always zero
        if settlement_type == "Advance":
            days_overdue = 0

        # 4. Interest calculation
        if days_overdue > 0:
            if interest_method == "simple":
                # Simple interest: P x r x t   (t = days / 365)
                interest_amount = round(
                    amount_settled * (interest_rate / 100) * (days_overdue / 365), 2
                )
            else:
                # Compound interest with monthly rests (MSMED Act default)
                interest_amount = _compound_interest_monthly_rests(
                    principal=amount_settled,
                    annual_rate_pct=interest_rate,
                    interest_start=due_date,
                    interest_end=effective_payment_date,
                )
        else:
            interest_amount = 0.0

        due_dates.append(due_date)
        days_overdue_list.append(days_overdue)
        interest_amounts.append(interest_amount)

    df["due_date"]                = due_dates
    df["days_overdue"]            = days_overdue_list
    df["annual_interest_rate"]    = round(interest_rate, 4)
    df["interest_method"]         = interest_method
    df["interest_bearing_amount"] = df["amount_settled"]
    df["interest_amount"]         = interest_amounts
    # Late-payment flag: True when any interest was charged
    df["is_late_payment"]         = df["days_overdue"] > 0

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: summarise results per vendor
# ─────────────────────────────────────────────────────────────────────────────

def summarise_by_vendor(result_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate the enriched ledger into one summary row per vendor.

    Input  : result_df from calculate_interest()
    Output : DataFrame with columns --
                 vendor_id, vendor_name,
                 total_purchases, total_payments,
                 total_settled_on_time, total_settled_late,
                 total_interest
    """
    if result_df.empty:
        return pd.DataFrame()

    rows = []
    for vendor_id, grp in result_df.groupby("vendor_id", sort=False):
        vendor_name = grp["vendor_name"].iloc[0]
        late_mask = grp["is_late_payment"]

        rows.append({
            "vendor_id":             vendor_id,
            "vendor_name":           vendor_name,
            "total_purchases":       round(grp["purchase_amount"].abs().sum(), 2),
            "total_payments":        round(
                                         grp.loc[grp["settlement_type"] != "Unsettled",
                                                  "amount_settled"].sum(), 2
                                     ),
            "total_settled_on_time": round(grp.loc[~late_mask, "amount_settled"].sum(), 2),
            "total_settled_late":    round(grp.loc[late_mask,  "amount_settled"].sum(), 2),
            "total_interest":        round(grp["interest_amount"].sum(), 2),
        })

    return pd.DataFrame(rows).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test / demo  (run: python msmed_core_engine.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Minimal demo dataset
    sample_data = {
        "vendor_id":    ["V001", "V001", "V001", "V002", "V002"],
        "vendor_name":  ["Alpha Supplies"] * 3 + ["Beta Corp"] * 2,
        "transactions": [-50000.0, -30000.0, 80000.0, -20000.0, 15000.0],
        "dates":        [
            "2024-01-10",   # V001 purchase 50 000
            "2024-02-15",   # V001 purchase 30 000
            "2024-04-01",   # V001 payment  80 000
            "2024-01-20",   # V002 purchase 20 000  (partially settled)
            "2024-04-10",   # V002 payment  15 000
        ],
    }

    df = pd.DataFrame(sample_data)
    df["dates"] = pd.to_datetime(df["dates"])

    print("=== Settlement Ledger ===")
    ledger = generate_settlement_ledger(df)
    print(ledger.to_string(index=False))

    print("\n=== Interest Calculation (compound, 19.5% p.a.) ===")
    result = calculate_interest(ledger, interest_rate=19.5, interest_method="compound")
    cols = [
        "vendor_id", "purchase_date", "payment_date", "settlement_type",
        "amount_settled", "due_date", "days_overdue",
        "interest_amount", "is_late_payment",
    ]
    print(result[cols].to_string(index=False))

    print("\n=== Vendor Summary ===")
    print(summarise_by_vendor(result).to_string(index=False))

