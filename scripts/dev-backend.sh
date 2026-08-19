#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend python -m uvicorn app.desktop_server:app --host 127.0.0.1 --port 8000
