@echo off
REM =============================================================================
REM build_windows.bat — Builds the Windows app AND the installer
REM
REM Requirements:
REM   1. Python 3.11+  → https://www.python.org/downloads/  (tick "Add to PATH")
REM   2. NSIS          → https://nsis.sourceforge.io/Download  (tick "Add to PATH")
REM
REM Output:
REM   dist\msme_calculator.exe        — standalone app (portable, no install needed)
REM   MSMED_Calculator_Setup.exe      — installer wizard (creates shortcuts, uninstaller)
REM =============================================================================

cd /D "%~dp0"

echo === MSMED Interest Calculator - Windows Build ===
echo.

REM ── Step 1: Virtual environment ──────────────────────────────────────────────
if not exist ".venv_build\" (
    echo [1/5] Creating build virtual environment...
    python -m venv .venv_build
    if errorlevel 1 ( echo ERROR: Python not found. Install Python 3.11+ and try again. & pause & exit /b 1 )
) else (
    echo [1/5] Build venv already exists, reusing.
)

REM ── Step 2: Install dependencies from requirements.txt ────────────────────────
echo [2/5] Installing dependencies from requirements.txt...
.venv_build\Scripts\python -m pip install --quiet --upgrade pip
.venv_build\Scripts\pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 ( echo ERROR: pip install failed. & pause & exit /b 1 )

REM ── Step 3: Build standalone .exe with PyInstaller ────────────────────────────
echo [3/5] Building standalone executable...
.venv_build\Scripts\pyinstaller msme_calculator.spec --clean --noconfirm
if errorlevel 1 ( echo ERROR: PyInstaller build failed. & pause & exit /b 1 )

if not exist "dist\msme_calculator.exe" (
    echo ERROR: dist\msme_calculator.exe not found after build.
    pause & exit /b 1
)
echo       Standalone app: dist\msme_calculator.exe

REM ── Step 4: Build installer with NSIS ─────────────────────────────────────────
echo [4/5] Building installer with NSIS...
where makensis >nul 2>&1
if errorlevel 1 (
    echo.
    echo [4/5] SKIPPED: NSIS not found on PATH.
    echo       To build the installer, install NSIS from https://nsis.sourceforge.io/Download
    echo       Then re-run this script.
    echo.
    goto :done
)
makensis installer.nsi
if errorlevel 1 ( echo ERROR: NSIS installer build failed. & pause & exit /b 1 )

REM ── Step 5: Done ─────────────────────────────────────────────────────────────
:done
echo [5/5] Build complete!
echo.
echo  Outputs:
if exist "dist\msme_calculator.exe"    echo   Portable app  : dist\msme_calculator.exe  (no install needed)
if exist "MSMED_Calculator_Setup.exe" echo   Installer     : MSMED_Calculator_Setup.exe (for end users)
echo.
echo  To share with users, distribute either file above.

pause
