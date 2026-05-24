#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

echo "==> PIDToolBox install"
echo "    Project root: $ROOT"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' not found. Install it and re-run install.sh." >&2
    exit 1
  fi
}

need_cmd python3
need_cmd pip3
need_cmd node
need_cmd npm

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ]]; then
  echo "ERROR: Python 3.11+ required (found $PY_VERSION)." >&2
  exit 1
fi

echo "==> Python $PY_VERSION, Node $(node -v), npm $(npm -v)"

echo "==> Installing backend (Python venv + dependencies)"
cd "$BACKEND"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip wheel setuptools
pip install -e ".[dev]"

echo "==> Installing frontend (npm dependencies)"
cd "$FRONTEND"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

echo "==> Generating golden test fixtures"
cd "$BACKEND"
python tests/export_golden.py

echo "==> Running backend tests"
pytest -q

echo "==> Building frontend"
cd "$FRONTEND"
npm run build

if command -v blackbox_decode >/dev/null 2>&1; then
  echo "==> blackbox_decode found: $(command -v blackbox_decode)"
else
  echo "==> NOTE: blackbox_decode not found on PATH."
  echo "    Install Betaflight blackbox tools to decode .BBL/.BFL files."
  echo "    CSV logs work without it."
fi

echo ""
echo "Install complete."
echo "  Start the app:  ./start.sh"
echo "  Backend API:    http://localhost:8000"
echo "  Frontend UI:    http://localhost:5173"
