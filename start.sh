#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

if [[ ! -d "$VENV" ]] || [[ ! -f "$VENV/bin/activate" ]]; then
  echo "ERROR: Backend venv not found. Run ./install.sh first." >&2
  exit 1
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "ERROR: Frontend dependencies not installed. Run ./install.sh first." >&2
  exit 1
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Stopping PIDToolBox..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "==> Starting PIDToolBox"
echo "    Backend:  http://localhost:8000"
echo "    Frontend: http://localhost:5173"
echo "    Press Ctrl+C to stop"
echo ""

cd "$BACKEND"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
uvicorn pidbox.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

cd "$FRONTEND"
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

wait
