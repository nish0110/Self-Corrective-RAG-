#!/usr/bin/env bash
# One-command start (macOS / Linux): builds the UI once, then serves everything on http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"
if [ ! -d frontend/dist ]; then (cd frontend && npm install && npm run build); fi
cd backend
[ -d .venv ] && source .venv/bin/activate
[ -f .env ] || cp .env.example .env
echo "Open http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
