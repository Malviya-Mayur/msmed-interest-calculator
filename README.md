# ⚖️ MSMED Act Interest Calculator

A standalone web application that calculates interest on **delayed payments to MSME vendors** as mandated by **Section 16 of the Micro, Small and Medium Enterprises Development (MSMED) Act, 2006**.

No Python, no server setup, no installation required for end users — just run the executable and the app opens in your browser.

---

## ⬇️ Downloads

| Platform | Download | Notes |
|---|---|---|
| 🐧 **Linux** (x86-64) | [**msme_calculator-linux-x86_64**](https://github.com/Malviya-Mayur/msmed-interest-calculator/releases/download/v1.1.0/msme_calculator-linux-x86_64) | Single file, no install needed |
| 🪟 **Windows** (x86-64) | [**msme_calculator-windows-x86_64.exe**](https://github.com/Malviya-Mayur/msmed-interest-calculator/releases/download/v1.1.0/msme_calculator-windows-x86_64.exe) | Single file, no install needed |

> 📦 View all releases: [github.com/…/releases](https://github.com/Malviya-Mayur/msmed-interest-calculator/releases)

---

## 🚀 Quick Start

### Linux
```bash
wget https://github.com/Malviya-Mayur/msmed-interest-calculator/releases/download/v1.1.0/msme_calculator-linux-x86_64
chmod +x msme_calculator-linux-x86_64
./msme_calculator-linux-x86_64
```

### Windows
```
Download and double-click msme_calculator.exe
```

The app starts a local server and opens your browser at `http://127.0.0.1:8000`.

---

## � Installation Guide

### 🐧 Linux

1. [Download `msme_calculator-linux-x86_64`](https://github.com/Malviya-Mayur/msmed-interest-calculator/releases/download/v1.1.0/msme_calculator-linux-x86_64)
2. Open a terminal in the download folder and run:
   ```bash
   chmod +x msme_calculator-linux-x86_64    # make it executable (one-time only)
   ./msme_calculator-linux-x86_64           # launch the app
   ```
3. Your browser opens automatically at `http://127.0.0.1:8000`
4. To stop the app, press **Ctrl-C** in the terminal

### 🪟 Windows

1. [Download `msme_calculator.exe`](https://github.com/Malviya-Mayur/msmed-interest-calculator/releases) from the Releases page
2. **Double-click** `msme_calculator.exe`
   - If Windows Defender SmartScreen appears, click **"More info" → "Run anyway"** (the app is safe — it's just unsigned)
3. A terminal window opens and your browser launches at `http://127.0.0.1:8000`
4. To stop the app, **close the terminal window**

> ⚠️ **Important:** Keep the terminal window open while using the app. Closing it shuts down the server.

---

## 🖥️ How to Use

1. **Upload your file** — drag & drop or browse for a `.csv` or `.xlsx` vendor ledger
   > **Note:** Your column names don't need to match exactly! A **Column Mapping** panel will appear, automatically detecting your columns (like `Amount` → `transactions`, `Supplier Code` → `vendor_id`).
2. **Set parameters:**
   - **Annual Interest Rate (%)** — typically 3× the RBI bank rate (e.g. RBI 6.5% → enter 19.5%)
   - **Credit Term (Days)** — statutory limit is 45 days; adjust only if a different agreed period applies
   - **Interest Method** — choose *Compound (Monthly Rests)* per MSMED Act, or *Simple Interest*
3. **Click Calculate Interest**
4. Review the **Vendor Summary** and **Detailed Settlement Ledger** on screen
5. **Download the Excel report** for a formatted, audit-ready file

---

## 📋 Input File Format

Upload a `.csv` or `.xlsx` file containing your vendor ledger data.

| Required Field | Type | Description |
|---|---|---|
| `vendor_id` | string | Vendor / supplier identifier |
| `transactions` | number | **Negative = Purchase / Invoice**, Positive = Payment received |
| `dates` | YYYY-MM-DD | Date of the transaction |

| Optional Field | Type | Description |
|---|---|---|
| `transaction_id` | string | Unique transaction ID / invoice number |
| `vendor_name` | string | Human-readable vendor name |
| `narration` | string | Free-text description / remarks |

> 💡 **Smart Column Mapping:** You do **not** need to rename your columns before uploading. The app will visually ask you to match your file's columns to these required fields. It even auto-detects common names automatically.
>
> A sample file (`Sample File.xlsx`) is included in the repository for reference. The app will also auto-detect the correct header row even if you have blank rows or titles at the top of your file.

---

## ⚖️ How Interest is Calculated

| Rule | Detail |
|---|---|
| Credit term | 45 days from invoice date (configurable) |
| Interest starts | Day after credit term expires |
| **Compound (MSMED Act)** | Monthly rests: `P × [(1 + r/12)^(months) − 1]` |
| **Simple interest** | `P × (rate/100) × (days/365)` |
| Settlement order | **FIFO** per vendor — oldest invoices settled first |
| Advance payments | Always zero interest (paid before invoice date) |

---

## 🛠️ Run from Source

Requires **Python 3.11+**.

```bash
# 1. Clone the repo
git clone https://github.com/Malviya-Mayur/msmed-interest-calculator.git
cd msmed-interest-calculator/msmed_calculator

# 2. Create a virtual environment and install dependencies
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## 🏗️ Build Standalone Executable

### Linux
```bash
cd msmed_calculator
bash build_linux.sh
# Output: dist/msme_calculator
```

### Windows *(run on a Windows machine with Python 3.11+ installed)*
```bat
cd msmed_calculator
build_windows.bat
rem Output: dist\msme_calculator.exe
```

Both scripts automatically create a clean virtual environment and install all dependencies from `requirements.txt` before building.

---

## 🧪 Run Tests

```bash
cd msmed_calculator
pytest tests/ -v
```

45 tests covering the settlement engine, interest formulas, and input validation — all must pass.

---

## 📁 Project Structure

```
msmed_calculator/
├── main.py              # FastAPI application entry point
├── config.py            # Constants (default rate, credit term)
├── launcher.py          # Standalone binary entry point
├── requirements.txt     # Runtime dependencies
├── msme_calculator.spec # PyInstaller build spec
├── build_linux.sh       # Linux build script
├── build_windows.bat    # Windows build script
├── ingestion/
│   ├── loader.py        # CSV/Excel reader (auto-detects header row)
│   └── validator.py     # Schema & data validation
├── engine/
│   ├── mapper.py        # FIFO settlement matching
│   ├── interest.py      # Compound & simple interest calculator
│   └── models.py        # Data models
├── output/
│   ├── reporter.py      # Build display DataFrames
│   └── exporter.py      # Excel export (openpyxl)
├── api/
│   └── routes.py        # HTTP route handlers
├── ui/
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS stylesheet
└── tests/               # 45 unit tests + fixtures
```

---

## 📄 Legal Reference

This tool implements the interest computation defined in **Section 16 of the MSMED Act, 2006**:

> *"Where any buyer fails to make payment of the amount to the supplier... the buyer shall, notwithstanding anything contained in any agreement between the buyer and the supplier... be liable to pay compound interest with monthly rests to the supplier on that amount from the appointed day or, as the case may be, from the date immediately following the date agreed upon, at three times of the bank rate notified by the Reserve Bank."*

---

## 🔒 Privacy

This application runs entirely **offline on your machine**. No data is transmitted to any external server. All calculations happen locally.
