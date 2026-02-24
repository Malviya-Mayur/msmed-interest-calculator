# msmed_calculator/api/routes.py
"""
FastAPI route handlers for the MSMED Interest Calculator.

Routes:
  GET  /          → Upload form (index.html)
  POST /calculate → Full pipeline: load → validate → map → interest → report → excel
  GET  /download  → Serve generated Excel file
  GET  /health    → Health check
"""

import os
import tempfile
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ingestion.loader import load_transactions
from ingestion.validator import validate, ValidationError
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


@router.post("/calculate", response_class=HTMLResponse)
async def calculate(
    request: Request,
    file: UploadFile = File(...),
    interest_rate: float = Form(...),
    credit_term_days: int = Form(CREDIT_TERM_DAYS),
    interest_method: str = Form("compound"),
):
    errors = []
    
    # ── 1. Save uploaded file to temp path ────────────────────────────────
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

        # ── 3. Validate ────────────────────────────────────────────────────
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

        # ── 4. Settlement Ledger ───────────────────────────────────────────
        ledger_df = generate_settlement_ledger(clean_df)

        if ledger_df.empty:
            errors.append("No settlement records could be generated from the uploaded file.")
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "errors": errors, "default_interest_rate": interest_rate},
            )

        # ── 5. Interest Calculation ────────────────────────────────────────
        interest_df = calculate_interest(
            ledger_df,
            interest_rate,
            credit_term_days=credit_term_days,
            interest_method=interest_method,
        )

        # ── 6. Build Reports ───────────────────────────────────────
        detailed_df = build_detailed_report(interest_df)
        summary_df = build_summary_report(interest_df, clean_df)

        # ── 7. Generate Excel and store in memory ──────────────────────────
        excel_bytes = export_to_excel(detailed_df, summary_df)
        _excel_store["data"] = excel_bytes
        _excel_store["filename"] = f"msmed_report_{file.filename.rsplit('.', 1)[0]}.xlsx"

        # ── 8. Render results page (first 100 rows) ────────────────────────
        # Convert to list-of-dicts for Jinja2 templating
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
        # Clean up temp file
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/download")
async def download():
    if _excel_store["data"] is None:
        raise HTTPException(status_code=404, detail="No report available. Please calculate first.")
    
    # Reset position for reading
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
