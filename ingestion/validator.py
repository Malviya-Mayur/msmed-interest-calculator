# msmed_calculator/ingestion/validator.py
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict


class ValidationError(Exception):
    """Raised when the input file has fatal structural problems."""
    pass


@dataclass
class ValidationResult:
    is_valid: bool
    clean_df: pd.DataFrame
    errors: List[str] = field(default_factory=list)


REQUIRED_COLUMNS = {"vendor_id", "transactions", "dates"}

# All fields the app knows about (required + optional)
ALL_FIELDS = [
    {"key": "vendor_id",      "label": "Vendor ID",       "required": True},
    {"key": "transactions",   "label": "Transactions",    "required": True},
    {"key": "dates",          "label": "Date",             "required": True},
    {"key": "vendor_name",    "label": "Vendor Name",     "required": False},
    {"key": "transaction_id", "label": "Transaction ID",  "required": False},
    {"key": "narration",      "label": "Narration",       "required": False},
]


def apply_column_mapping(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """
    Rename DataFrame columns according to the user-supplied mapping.

    mapping: {user_column_name: target_internal_name}
    e.g. {"Supplier Code": "vendor_id", "Invoice Amt": "transactions"}

    - Only renames columns present in the mapping AND in df.
    - Columns not in the mapping are left unchanged.
    - Empty string values in mapping are ignored (user chose "skip").
    """
    if not mapping:
        return df

    # Filter to only valid, non-empty mappings where the source col actually exists
    rename_map = {
        src: tgt
        for src, tgt in mapping.items()
        if src and tgt and src in df.columns
    }

    return df.rename(columns=rename_map)


def validate(df: pd.DataFrame) -> ValidationResult:
    """
    Validate and coerce the raw DataFrame.
    Returns a ValidationResult with clean_df and any non-fatal row errors.
    Raises ValidationError for fatal structural problems.
    """
    errors: List[str] = []

    # ── 1. Check required columns ──────────────────────────────────────────
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValidationError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"File must contain: {', '.join(sorted(REQUIRED_COLUMNS))}."
        )

    df = df.copy()

    # ── 2. Coerce transactions to float ────────────────────────────────────
    before = len(df)
    df["transactions"] = pd.to_numeric(df["transactions"], errors="coerce").astype("float64")
    unparseable_amounts = df["transactions"].isna().sum()
    if unparseable_amounts:
        errors.append(
            f"{unparseable_amounts} row(s) had non-numeric 'transactions' values and were dropped."
        )
    df = df.dropna(subset=["transactions"])

    # ── 3. Drop zero-amount rows ───────────────────────────────────────────
    zero_rows = (df["transactions"] == 0).sum()
    if zero_rows:
        errors.append(f"{zero_rows} row(s) with zero transaction amount were dropped.")
    df = df[df["transactions"] != 0]

    # ── 4. Coerce dates ────────────────────────────────────────────────────
    df["dates"] = pd.to_datetime(df["dates"], dayfirst=False, errors="coerce")
    unparseable_dates = df["dates"].isna().sum()
    if unparseable_dates:
        errors.append(
            f"{unparseable_dates} row(s) had unparseable 'dates' values and were dropped."
        )
    df = df.dropna(subset=["dates"])

    # ── 5. Ensure vendor_id is a string (fallback: single vendor) ─────────
    if "vendor_id" not in df.columns or df["vendor_id"].isna().all():
        df["vendor_id"] = "VENDOR_01"
        errors.append("'vendor_id' column missing or empty — all rows treated as a single vendor.")
    else:
        df["vendor_id"] = df["vendor_id"].astype(str).str.strip()

    # ── 6. Ensure vendor_name exists ──────────────────────────────────────
    if "vendor_name" not in df.columns:
        df["vendor_name"] = df["vendor_id"]
    else:
        df["vendor_name"] = df["vendor_name"].fillna(df["vendor_id"])

    # ── 7. Must have at least one inflow and one outflow ──────────────────
    if len(df) == 0:
        raise ValidationError("No valid rows remain after cleaning. Please check your file.")

    has_inflow = (df["transactions"] > 0).any()
    has_outflow = (df["transactions"] < 0).any()
    if not has_inflow:
        raise ValidationError(
            "File must contain at least one positive (payment/inflow) transaction."
        )
    if not has_outflow:
        raise ValidationError(
            "File must contain at least one negative (purchase/outflow) transaction."
        )

    # ── 8. Reset index ─────────────────────────────────────────────────────
    df = df.reset_index(drop=True)

    return ValidationResult(is_valid=True, clean_df=df, errors=errors)
