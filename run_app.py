"""
Standalone executable entry point for GrainSight.

When frozen by PyInstaller, this script:
1. Sets the working directory to the executable's location
2. Starts the embedded FastAPI/Uvicorn server
3. Opens the default browser at http://127.0.0.1:8010

Usage (development):
    python run_app.py [--port 8010] [--no-browser]

Usage (frozen):
    ./FASL_3D_GrainSize.exe [--port 8010] [--no-browser]
"""
import sys
import os
import argparse
import webbrowser
import threading
from pathlib import Path


def _exe_dir() -> Path:
    """Return the directory containing the executable (frozen) or script (dev)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="GrainSight -- 3D Particle Size & Granulometry Analyzer")
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()

    os.chdir(str(_exe_dir()))

    import uvicorn
    from app.main import app

    url = f"http://{args.host}:{args.port}"
    print(f"Starting GrainSight at {url}")

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
