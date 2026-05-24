#!/usr/bin/env bash
# Stop PIDToolBox backend (uvicorn :8000) and frontend (vite :5173).
set -euo pipefail

BACKEND_PORT=8000
FRONTEND_PORT=5173

kill_port() {
  local port=$1
  local label=$2
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser -n tcp "$port" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true)"
  fi

  if [[ -z "$pids" ]]; then
    echo "    $label (port $port): not running"
    return 0
  fi

  echo "==> Stopping $label (port $port)..."
  # shellcheck disable=SC2086
  kill -TERM $pids 2>/dev/null || true
  sleep 0.5
  # shellcheck disable=SC2086
  kill -KILL $pids 2>/dev/null || true
}

echo "==> Stopping PIDToolBox"

kill_port "$BACKEND_PORT" "backend"
kill_port "$FRONTEND_PORT" "frontend"

# Catch reload workers / npm wrappers not bound to the port yet
pkill -f "uvicorn pidbox.main:app" 2>/dev/null || true
pkill -f "vite.*5173" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true

echo "Done."
