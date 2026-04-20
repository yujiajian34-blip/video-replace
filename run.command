#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x ".venv/bin/python" ]; then
    echo "[INFO] Python virtual environment not found."
    echo "[INFO] Running setup first..."
    bash "$SCRIPT_DIR/setup.command"
fi

if ! ".venv/bin/python" -c "import flask, flask_cors, requests" >/dev/null 2>&1; then
    echo "[INFO] Required packages are missing."
    echo "[INFO] Running setup first..."
    bash "$SCRIPT_DIR/setup.command"
fi

echo
echo "========================================"
echo "  Video Role Replace Tool (macOS)"
echo "  URL: http://127.0.0.1:5001"
echo "  Press Ctrl+C to stop"
echo "========================================"
echo

(
    sleep 3
    open "http://127.0.0.1:5001" >/dev/null 2>&1 || true
) &

exec ".venv/bin/python" "backend/app.py"
