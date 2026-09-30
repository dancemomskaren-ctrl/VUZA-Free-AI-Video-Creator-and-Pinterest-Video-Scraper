#!/usr/bin/env bash
# VUZA launcher — uses the local venv and starts the server.
# Usage: ./start.sh            (port defaults to 8000)
#        PORT=8001 ./start.sh  (custom port)
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "🛠  No venv found — creating one and installing dependencies..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/playwright install chromium
fi

echo "🚀 Starting VUZA on http://localhost:${PORT:-8000}"
exec ./venv/bin/python app.py
