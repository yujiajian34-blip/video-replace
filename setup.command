#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Video Role Replace Tool Setup (macOS)"
echo "========================================"

PYTHON_CMD=""

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3.10+ was not found."
    echo "[INFO] Install Python from:"
    echo "       https://www.python.org/downloads/macos/"
    exit 1
fi

echo "Using: $PYTHON_CMD"
echo

if [ -d ".venv" ] && [ ! -x ".venv/bin/python" ]; then
    echo "[INFO] Found incomplete virtual environment. Recreating..."
    rm -rf ".venv"
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] Creating virtual environment..."
    "$PYTHON_CMD" -m venv .venv
else
    echo "[1/3] Virtual environment already exists."
fi

echo "[2/3] Upgrading pip..."
".venv/bin/python" -m pip install --upgrade pip

echo "[3/3] Installing dependencies..."
".venv/bin/python" -m pip install -r requirements.txt

echo
echo "Setup completed successfully."
echo "You can now double-click run.command"
echo
read -r -p "Press Enter to close..."
