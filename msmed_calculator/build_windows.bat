@echo off
REM =============================================================================
REM build_windows.bat — Builds the Windows standalone executable
REM Usage: Double-click or run from CMD in this folder
REM Output: dist\msme_calculator.exe  (single file, no Python required to run)
REM
REM Requirements: Python 3.11+ installed and on PATH
REM   Download: https://www.python.org/downloads/
REM   Tick "Add Python to PATH" during install.
REM =============================================================================

cd /D "%~dp0"

echo === MSMED Interest Calculator - Windows Build ===
echo.

REM 1. Create virtual environment
if not exist ".venv_build\" (
    echo [1/4] Creating build virtual environment...
    python -m venv .venv_build
) else (
    echo [1/4] Build venv already exists, reusing.
)

REM 2. Install dependencies from requirements.txt + pyinstaller
echo [2/4] Installing dependencies from requirements.txt...
.venv_build\Scripts\python -m pip install --quiet --upgrade pip
.venv_build\Scripts\pip install --quiet -r requirements.txt pyinstaller

REM 3. Run PyInstaller
echo [3/4] Building executable with PyInstaller...
.venv_build\Scripts\pyinstaller msme_calculator.spec --clean --noconfirm

REM 4. Verify output
if exist "dist\msme_calculator.exe" (
    echo.
    echo [4/4] Build successful!
    echo       Output : dist\msme_calculator.exe
    echo       Run    : Double-click dist\msme_calculator.exe
) else (
    echo [4/4] ERROR: dist\msme_calculator.exe not found. Check output above.
    exit /b 1
)

pause
