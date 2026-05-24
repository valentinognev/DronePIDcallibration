#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Backend
cd "$ROOT/backend"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -e ".[dev]" -q

# Frontend
cd "$ROOT/frontend"
npm install -q

# Start both
cd "$ROOT/backend"
source .venv/bin/activate
uvicorn pidbox.main:app --reload --port 8000 &
BACKEND_PID=$!

cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
