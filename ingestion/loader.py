# msmed_calculator/ingestion/loader.py
import pandas as pd
from pathlib import Path
from typing import List

# Columns that must appear (lowercased) to identify the real header row
_REQUIRED_HEADER_COLS = {"transactions", "dates", "vendor_id"}


def _find_header_row(file_path, suffix: str) -> int:
    """
    Scan the first 10 rows of a file and return the 0-indexed row number
    where the real column headers are found. Returns 0 if not found (default).

    This handles Excel files that have blank rows or a title row above the
    actual column headers (very common in real-world exports).
    """
    for row in range(10):
        try:
            if suffix == ".csv":
                probe = pd.read_csv(file_path, header=row, nrows=1, dtype=str)
            else:
                probe = pd.read_excel(file_path, header=row, nrows=1, dtype=str)
            cols = {str(c).strip().lower() for c in probe.columns}
            if _REQUIRED_HEADER_COLS.issubset(cols):
                return row
        except Exception:
            break
    return 0


def load_transactions(file_path: str) -> pd.DataFrame:
    """
    Accept a file path or file-like object.
    Return a raw pandas DataFrame with parsed dates and stripped strings.
    Supports .csv, .xlsx, .xls.

    Automatically skips leading blank or title rows to find the real header.
    """
    path = Path(file_path) if isinstance(file_path, str) else None

    if path is not None:
        suffix = path.suffix.lower()
    else:
        suffix = ".csv"

    if suffix not in (".csv", ".xlsx", ".xls"):
        raise ValueError(f"Unsupported file type: '{suffix}'. Please upload a .csv or .xlsx file.")

    header_row = _find_header_row(file_path, suffix)

    if suffix == ".csv":
        df = pd.read_csv(file_path, header=header_row, dtype=str)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, header=header_row, dtype=str)

    # Strip whitespace from all column names
    df.columns = [c.strip() for c in df.columns]

    # Strip whitespace from all string values
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Parse dates column
    if "dates" in df.columns:
        df["dates"] = pd.to_datetime(df["dates"], dayfirst=False, errors="coerce")

    return df


def load_raw_columns(file_path: str) -> List[str]:
    """
    Return only the column names of the uploaded file without full parsing.
    Used by the /preview-columns endpoint to populate the mapping UI.
    Handles leading blank/title rows using the same heuristic as load_transactions.
    """
    path = Path(file_path) if isinstance(file_path, str) else None
    suffix = path.suffix.lower() if path else ".csv"

    if suffix not in (".csv", ".xlsx", ".xls"):
        raise ValueError(f"Unsupported file type: '{suffix}'.")

    # Try to locate the real header row first; fall back to row 0
    header_row = _find_header_row(file_path, suffix)

    if suffix == ".csv":
        probe = pd.read_csv(file_path, header=header_row, nrows=0, dtype=str)
    else:
        probe = pd.read_excel(file_path, header=header_row, nrows=0, dtype=str)

    # Return cleaned column names (strip whitespace)
    return [str(c).strip() for c in probe.columns]
