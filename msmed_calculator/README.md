# MSMED Act Interest Calculator

A production-ready web application that calculates interest on delayed payments to MSME vendors per **Section 16 of the Micro, Small and Medium Enterprises Development (MSMED) Act, 2006**.

## Features

- 📂 Upload vendor transaction data as **CSV or Excel (.xlsx)**
- ⚖️ FIFO settlement ledger — maps purchases to payments chronologically
- 💰 Correct identification of **Advance** vs **Standard** settlements
- 📊 Per-vendor interest calculation at **3× the RBI bank rate** (simple interest)
- 📋 Detailed auditable ledger + per-vendor summary report
- ⬇️ Excel export with two sheets, bold headers, and red-highlighted interest rows
- 🛡️ Graceful error handling — never crashes on bad input

---

## Setup

```bash
# 1. Navigate to the project directory
cd msmed_calculator

# 2. (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Run the Application

```bash
# From the msmed_calculator/ directory
uvicorn main:app --reload --port 8000
```

Then open your browser at **http://localhost:8000**

---

## Run Tests

```bash
# From the msmed_calculator/ directory
pytest tests/ -v
```

All tests must pass, including assertions that match the exact worked example from Section 6 of the spec (V01 total interest = ₹5,773.82).

---

## Input File Format

The application accepts `.csv` or `.xlsx` files with the following columns:

| Column | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | string | No | Unique identifier |
| `vendor_id` | string | **Yes** | Vendor identifier |
| `vendor_name` | string | No | Human-readable vendor name |
| `transactions` | float | **Yes** | Negative = Purchase, Positive = Payment |
| `dates` | YYYY-MM-DD | **Yes** | Transaction date |
| `narration` | string | No | Free-text description |

---

## Key Business Rules (MSMED Act Section 16)

| Rule | Detail |
|---|---|
| Credit term | 45 days from purchase date |
| Interest start | Day 46 onward |
| Interest rate | **3× RBI bank rate** |
| Interest type | Simple interest, 365-day year |
| Formula | `amount × (rate/100) × (days/365)` |
| Advances | Never late — zero interest always |
| Settlement order | FIFO (chronological) per vendor |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Upload form |
| POST | `/calculate` | Run full pipeline |
| GET | `/download` | Download Excel report |
| GET | `/health` | Health check (`{"status": "ok"}`) |

---

## Project Structure

```
msmed_calculator/
├── main.py                    # FastAPI entry point
├── config.py                  # App constants
├── requirements.txt
├── ingestion/
│   ├── loader.py              # CSV/Excel reader
│   └── validator.py           # Schema validation
├── engine/
│   ├── models.py              # LedgerRow, SummaryRow dataclasses
│   ├── mapper.py              # FIFO settlement ledger
│   └── interest.py            # Interest calculator
├── output/
│   ├── reporter.py            # Build display DataFrames
│   └── exporter.py            # Excel export (openpyxl)
├── api/
│   └── routes.py              # FastAPI route handlers
├── ui/
│   ├── templates/
│   │   ├── index.html         # Upload form
│   │   └── results.html       # Results + download
│   └── static/
│       └── style.css
└── tests/
    ├── test_mapper.py
    ├── test_interest.py
    ├── test_validator.py
    └── fixtures/
        └── sample_transactions.csv
```
