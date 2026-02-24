# msmed_calculator/main.py
"""
FastAPI application entry point for the MSMED Act Interest Calculator.

Run with:
    uvicorn main:app --reload --port 8000
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from api.routes import router
from config import APP_TITLE, APP_VERSION, get_base_dir

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=(
        "Calculates interest on delayed MSME payments per "
        "Section 16 of the Micro, Small and Medium Enterprises Development (MSMED) Act, 2006."
    ),
)

# Mount static files
BASE_DIR = get_base_dir()
static_dir = os.path.join(BASE_DIR, "ui", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register routes
app.include_router(router)
