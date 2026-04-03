#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copy .env.example to .env and fill in your credentials."
    exit 1
fi

echo "Installing dependencies…"
pip install -q -r requirements.txt

echo "Starting Analytics Chat…"
streamlit run ui/streamlit_app.py --server.headless true
