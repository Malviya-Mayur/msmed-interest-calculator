# msmed_calculator/launcher.py
"""
PyInstaller entry point for the MSMED Act Interest Calculator.

This script:
  1. Starts uvicorn on a free port (default 8000, fallbacks to 8001+)
  2. Waits for the server to be ready
  3. Opens the browser automatically
  4. Keeps running until the user closes the terminal / presses Ctrl-C

Build (Linux):
    .venv_build/bin/pyinstaller msme_calculator.spec --clean

Build (Windows — run from a Windows machine with Python installed):
    pyinstaller msme_calculator.spec --clean
"""

import sys
import os
import time
import socket
import threading
import webbrowser

# ── resolve base directory (handles both dev and frozen/PyInstaller) ──────────
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure our package root is on sys.path so `import main`, `import config`, etc. work
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _find_free_port(start: int = 8000, attempts: int = 10) -> int:
    """Return the first available TCP port starting from `start`."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}–{start + attempts - 1}")


def _wait_for_server(port: int, timeout: float = 20.0) -> bool:
    """Poll until the server is accepting connections or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.25)
    return False


def _run_server(port: int) -> None:
    """
    Import and run the FastAPI app directly (no subprocess).
    Importing `main` here works because BASE_DIR is already in sys.path,
    and all bundled modules are available via PyInstaller's import machinery.
    """
    import uvicorn
    # Import the app object directly — avoids uvicorn trying to locate 'main' as a file
    from main import app  # noqa: F401 — loaded here to trigger module registration
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",   # keep console quiet for end-users
    )


def main() -> None:
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    print(f"Starting MSMED Interest Calculator …")
    print(f"Opening browser at {url}")
    print("Press Ctrl-C (or close this window) to stop.\n")

    # Start the server in a background daemon thread
    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for the server to be ready, then open the browser
    if _wait_for_server(port):
        webbrowser.open(url)
    else:
        print(f"[Warning] Server did not start within 20 s — open {url} manually.")

    # Keep the main thread alive until Ctrl-C or the server thread dies
    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
