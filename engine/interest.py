# msmed_calculator/engine/interest.py
"""
Interest calculation per MSMED Act, Section 16.

The Act mandates COMPOUND INTEREST WITH MONTHLY RESTS:
  "the buyer shall be liable to pay compound interest with monthly rests
   to the supplier on that amount from the appointed day..."

Algorithm:
  1. Due date = purchase_date + 45 days (credit term)
  2. Interest accrues from due_date onward (day 46+)
  3. Monthly rate  = annual_rate / 12
  4. For each complete calendar month overdue, compound the balance.
  5. For remaining partial-month days, apply simple interest on the
     compounded balance proportional to days / days_in_that_month.
  6. Advances (payment before purchase) → days_overdue = 0, interest = 0.
  7. Unsettled purchases → interest accrues to today's date.
"""

import calendar
import pandas as pd
from datetime import date, timedelta
from config import CREDIT_TERM_DAYS


# ── helpers ──────────────────────────────────────────────────────────────────

def _add_months(d: date, n: int) -> date:
    """Add n calendar months to date d, clamping the day if the target month is shorter."""
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

    Args:
        principal:        Amount on which interest is charged.
        annual_rate_pct:  Annual interest rate as a percentage (e.g. 19.5).
        interest_start:   Date from which interest starts accruing (the due date).
        interest_end:     Date on which interest stops (payment date / today).

    Returns:
        Interest amount rounded to 2 decimal places.
    """
    if interest_end <= interest_start:
        return 0.0

    monthly_rate = annual_rate_pct / 100 / 12

    # ── Step 1: Count complete calendar months ───────────────────────────────
    complete_months = 0
    boundary = interest_start
    while True:
        next_boundary = _add_months(interest_start, complete_months + 1)
        if next_boundary <= interest_end:
            complete_months += 1
            boundary = next_boundary
        else:
            break

    # ── Step 2: Compound balance after complete months ───────────────────────
    balance = principal * ((1 + monthly_rate) ** complete_months)

    # ── Step 3: Simple interest on remainder (partial month) ─────────────────
    remaining_days = (interest_end - boundary).days
    if remaining_days > 0:
        days_in_month = calendar.monthrange(boundary.year, boundary.month)[1]
        balance += balance * monthly_rate * (remaining_days / days_in_month)

    return round(balance - principal, 2)


# ── main function ─────────────────────────────────────────────────────────────

def calculate_interest(
    ledger_df: pd.DataFrame,
    interest_rate: float,
    credit_term_days: int = CREDIT_TERM_DAYS,
    interest_method: str = "compound",
) -> pd.DataFrame:
    """
    Enrich the settlement ledger with interest calculation columns.

    Args:
        ledger_df:        Settlement ledger from engine/mapper.py.
        interest_rate:    Annual interest rate in % (entered directly by user).
        credit_term_days: Credit period in days (default 45 per MSMED Act).
        interest_method:  'compound' (monthly rests, MSMED Act default)
                          or 'simple' (flat daily accrual).

    Returns:
        DataFrame with added columns:
          due_date, days_overdue, annual_interest_rate,
          interest_bearing_amount, interest_amount, interest_method
    """
    if ledger_df.empty:
        return ledger_df

    df = ledger_df.copy()
    today = date.today()

    due_dates = []
    days_overdue_list = []
    interest_amounts = []

    for _, row in df.iterrows():
        purchase_date = row["purchase_date"]
        if isinstance(purchase_date, pd.Timestamp):
            purchase_date = purchase_date.date()

        settlement_type = row["settlement_type"]
        amount_settled = float(row["amount_settled"])

        # ── 1. Due date ───────────────────────────────────────────────────────
        due_date = purchase_date + timedelta(days=credit_term_days)

        # ── 2. Effective payment date ─────────────────────────────────────────
        if settlement_type == "Advance":
            # Advances are never overdue — force days_overdue = 0
            effective_payment_date = due_date
        elif settlement_type == "Unsettled":
            effective_payment_date = today
        else:
            payment_date = row["payment_date"]
            if isinstance(payment_date, pd.Timestamp):
                payment_date = payment_date.date()
            effective_payment_date = payment_date

        # ── 3. Days overdue (for display) ────────────────────────────────────
        days_overdue = max(0, (effective_payment_date - due_date).days)

        # Hard guard: Advances always zero
        if settlement_type == "Advance":
            days_overdue = 0

        # ── 4. Interest calculation ────────────────────────────────────────────────
        if days_overdue > 0:
            if interest_method == "simple":
                # Simple interest: P × r × t  (t = days/365)
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

    df["due_date"] = due_dates
    df["days_overdue"] = days_overdue_list
    df["annual_interest_rate"] = round(interest_rate, 4)
    df["interest_method"] = interest_method
    df["interest_bearing_amount"] = df["amount_settled"]
    df["interest_amount"] = interest_amounts

    return df
