# msmed_calculator/api/routes.py
"""
FastAPI route handlers for the MSMED Interest Calculator.

Routes:
  GET  /               → Upload form (index.html)
  POST /preview-columns→ Return JSON list of column names from uploaded file
  POST /calculate      → Full pipeline: load → map → validate → interest → report → excel
  GET  /download       → Serve generated Excel file
  GET  /health         → Health check
"""

import os
import tempfile
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ingestion.loader import load_transactions, load_raw_columns
from ingestion.validator import validate, apply_column_mapping, ValidationError, ALL_FIELDS
from engine.mapper import generate_settlement_ledger
from engine.interest import calculate_interest
from output.reporter import build_detailed_report, build_summary_report
from output.exporter import export_to_excel
from config import DEFAULT_INTEREST_RATE, CREDIT_TERM_DAYS, get_base_dir

router = APIRouter()

# Templates — resolved via get_base_dir() so it works both in dev and as a frozen binary
BASE_DIR = get_base_dir()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "ui", "templates"))

# In-memory store for the generated Excel file (simple single-user approach)
_excel_store: dict = {"data": None, "filename": "msmed_interest_report.xlsx"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_interest_rate": DEFAULT_INTEREST_RATE,
            "default_credit_term": CREDIT_TERM_DAYS,
        },
    )


@router.post("/preview-columns")
async def preview_columns(file: UploadFile = File(...)):
    """
    Accept a file upload and return its column names as JSON.
    Does NOT store the file or perform any validation — purely for populating
    the column-mapping UI on the frontend.
    """
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Please upload a .csv or .xlsx file.",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        columns = load_raw_columns(tmp_path)
        return JSONResponse({"columns": columns, "filename": file.filename})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@router.post("/calculate", response_class=HTMLResponse)
async def calculate(
    request: Request,
    file: UploadFile = File(...),
    interest_rate: float = Form(...),
    credit_term_days: int = Form(CREDIT_TERM_DAYS),
    interest_method: str = Form("compound"),
    # ── Column mapping fields (all optional) ─────────────────────────────
    map_vendor_id: Optional[str] = Form(None),
    map_transactions: Optional[str] = Form(None),
    map_dates: Optional[str] = Form(None),
    map_vendor_name: Optional[str] = Form(None),
    map_transaction_id: Optional[str] = Form(None),
    map_narration: Optional[str] = Form(None),
):
    errors = []

    # ── 1. Validate file type ──────────────────────────────────────────────
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        errors.append(f"Unsupported file type '{suffix}'. Please upload a .csv or .xlsx file.")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "errors": errors, "default_interest_rate": interest_rate,
             "default_credit_term": credit_term_days},
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # ── 2. Load ────────────────────────────────────────────────────────
        raw_df = load_transactions(tmp_path)

        # ── 3. Apply column mapping (if provided) ──────────────────────────
        # Build a {user_col → internal_col} dict from the submitted form fields.
        # Empty / None values mean "skip this field".
        column_mapping = {}
        mapping_pairs = [
            (map_vendor_id,      "vendor_id"),
            (map_transactions,   "transactions"),
            (map_dates,          "dates"),
            (map_vendor_name,    "vendor_name"),
            (map_transaction_id, "transaction_id"),
            (map_narration,      "narration"),
        ]
        for user_col, internal_col in mapping_pairs:
            if user_col and user_col.strip():
                column_mapping[user_col.strip()] = internal_col

        if column_mapping:
            raw_df = apply_column_mapping(raw_df, column_mapping)

        # ── 4. Validate ────────────────────────────────────────────────────
        try:
            validation_result = validate(raw_df)
        except ValidationError as e:
            errors.append(str(e))
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "errors": errors, "default_interest_rate": interest_rate,
                 "default_credit_term": credit_term_days},
            )

        clean_df = validation_result.clean_df
        if validation_result.errors:
            errors.extend(validation_result.errors)

        # ── 5. Settlement Ledger ───────────────────────────────────────────
        ledger_df = generate_settlement_ledger(clean_df)

        if ledger_df.empty:
            errors.append("No settlement records could be generated from the uploaded file.")
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "errors": errors, "default_interest_rate": interest_rate},
            )

        # ── 6. Interest Calculation ────────────────────────────────────────
        interest_df = calculate_interest(
            ledger_df,
            interest_rate,
            credit_term_days=credit_term_days,
            interest_method=interest_method,
        )

        # ── 7. Build Reports ───────────────────────────────────────────────
        detailed_df = build_detailed_report(interest_df)
        summary_df = build_summary_report(interest_df, clean_df)

        # ── 8. Generate Excel and store in memory ──────────────────────────
        excel_bytes = export_to_excel(detailed_df, summary_df)
        _excel_store["data"] = excel_bytes
        _excel_store["filename"] = f"msmed_report_{file.filename.rsplit('.', 1)[0]}.xlsx"

        # ── 9. Render results page (first 100 rows) ────────────────────────
        detailed_preview = detailed_df.head(100).to_dict(orient="records")
        summary_records = summary_df.to_dict(orient="records")
        total_rows = len(detailed_df)

        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "summary": summary_records,
                "ledger": detailed_preview,
                "ledger_columns": list(detailed_df.columns),
                "summary_columns": list(summary_df.columns),
                "interest_rate": interest_rate,
                "credit_term_days": credit_term_days,
                "interest_method": interest_method,
                "total_rows": total_rows,
                "showing_rows": min(100, total_rows),
                "warnings": errors,
                "filename": file.filename,
            },
        )

    except Exception as e:
        errors.append(f"An unexpected error occurred: {str(e)}")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "errors": errors, "default_interest_rate": interest_rate,
             "default_credit_term": credit_term_days},
        )
    finally:
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/download")
async def download():
    if _excel_store["data"] is None:
        raise HTTPException(status_code=404, detail="No report available. Please calculate first.")

    excel_io: BytesIO = _excel_store["data"]
    excel_io.seek(0)

    return StreamingResponse(
        excel_io,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{_excel_store["filename"]}"'
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
