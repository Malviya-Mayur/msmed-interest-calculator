#!/bin/bash
# =============================================================================
# build_linux.sh — Builds the Linux standalone executable
# Usage: bash build_linux.sh
# Output: dist/msme_calculator  (single file, no Python required to run)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== MSMED Interest Calculator — Linux Build ==="
echo ""

# 1. Create a lean virtual environment
if [ ! -d ".venv_build" ]; then
  echo "[1/4] Creating build virtual environment..."
  python3 -m venv .venv_build
else
  echo "[1/4] Build venv already exists, reusing."
fi

# 2. Install dependencies from requirements.txt + pyinstaller
echo "[2/4] Installing dependencies from requirements.txt..."
.venv_build/bin/pip install --quiet --upgrade pip
.venv_build/bin/pip install --quiet -r requirements.txt pyinstaller

# 3. Run PyInstaller
echo "[3/4] Building executable with PyInstaller..."
.venv_build/bin/pyinstaller msme_calculator.spec --clean --noconfirm 2>&1 | grep -E "(INFO|WARNING|ERROR|completed|Build)" || true

# 4. Verify output
if [ -f "dist/msme_calculator" ]; then
  SIZE=$(du -sh dist/msme_calculator | cut -f1)
  echo ""
  echo "[4/4] Build successful!"
  echo "      Output : dist/msme_calculator  ($SIZE)"
  echo "      Run    : ./dist/msme_calculator"
else
  echo "[4/4] ERROR: dist/msme_calculator not found. Check output above."
  exit 1
fi
