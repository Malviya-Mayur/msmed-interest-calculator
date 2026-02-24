import sys
import os

CREDIT_TERM_DAYS = 45          # Statutory credit term per MSMED Act
DEFAULT_INTEREST_RATE = 19.5   # Default annual interest rate in % (user can override)
INTEREST_MULTIPLIER = 3        # Kept for reference — per MSMED Act, rate = 3× bank rate
DATE_FORMAT = "%Y-%m-%d"
APP_TITLE = "MSMED Act Interest Calculator"
APP_VERSION = "1.0.0"


def get_base_dir() -> str:
    """
    Return the project root directory.
    - When running normally:          directory containing this file.
    - When frozen by PyInstaller:     sys._MEIPASS (the temp extraction dir).
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))
