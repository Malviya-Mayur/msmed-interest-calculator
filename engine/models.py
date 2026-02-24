# msmed_calculator/engine/models.py
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class LedgerRow:
    vendor_id: str
    vendor_name: str
    purchase_index: int
    purchase_date: date
    purchase_amount: float        # Always negative
    payment_index: Optional[int]
    payment_date: Optional[date]
    amount_settled: float         # Always positive
    settlement_type: str          # 'Advance' or 'Standard'
    due_date: date                # purchase_date + 45 days
    days_overdue: int             # max(0, (payment_date - due_date).days)
    interest_bearing_amount: float
    annual_interest_rate: float   # 3 × bank_rate
    interest_amount: float        # Simple interest for days_overdue


@dataclass
class SummaryRow:
    vendor_id: str
    vendor_name: str
    total_purchases: float
    total_payments: float
    total_settled_on_time: float
    total_settled_late: float
    total_interest: float
