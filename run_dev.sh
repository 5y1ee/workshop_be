#!/usr/bin/env bash
#
# Mac 기준 실행 예시:
#   ./run_dev.sh --install        # 의존성 설치 후 백엔드/프론트 실행.
#   ./run_dev.sh --backend-only   # 백엔드만 실행.
#   ./run_dev.sh --frontend-only  # 프론트만 실행.
#   ./run_dev.sh --backend-port 8001 --frontend-port 5174

# python -m scripts.seed_db reset-seed --yes

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
RUN_BACKEND=1
RUN_FRONTEND=1
INSTALL_DEPS=0

usage() {
  cat <<'EOF'
Usage:
  ./run_dev.sh [options]

Options:
  --install              Install Python and frontend dependencies before running.
  --backend-only         Run only the FastAPI backend.
  --frontend-only        Run only the Vite frontend.
  --host HOST            Bind host. Default: 127.0.0.1
  --backend-port PORT    Backend port. Default: 8000
  --frontend-port PORT   Frontend port. Default: 5173
  -h, --help             Show this help.

Environment overrides:
  PYTHON_BIN             Python executable to use. Default: python
  VITE_API_BASE          Frontend API base URL. Default: http://HOST:BACKEND_PORT
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      INSTALL_DEPS=1
      shift
      ;;
    --backend-only)
      RUN_FRONTEND=0
      shift
      ;;
    --frontend-only)
      RUN_BACKEND=0
      shift
      ;;
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:?--backend-port requires a value}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:?--frontend-port requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    exit 1
  fi
}

install_deps() {
  echo "[setup] Installing backend dependencies into: $("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
  (cd "$ROOT_DIR" && "$PYTHON_BIN" -m pip install -r requirements-dev.txt)

  echo "[setup] Installing frontend dependencies"
  (cd "$ROOT_DIR/frontend" && npm install)
}

check_backend_deps() {
  "$PYTHON_BIN" - <<'PY'
import importlib
import sys

missing = []
for name in ("fastapi", "sqlalchemy", "asyncpg", "greenlet", "uvicorn"):
    try:
        importlib.import_module(name)
    except ImportError:
        missing.append(name)

if missing:
    print("Missing Python packages: " + ", ".join(missing), file=sys.stderr)
    print("Run: ./run_dev.sh --install", file=sys.stderr)
    raise SystemExit(1)
PY
}

normalized_database_url() {
  (cd "$ROOT_DIR" && "$PYTHON_BIN" - <<'PY')
import os
import sys

from dotenv import dotenv_values
from sqlalchemy import make_url

raw = os.environ.get("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
if not raw:
    print("DATABASE_URL was not found in environment or .env", file=sys.stderr)
    raise SystemExit(1)

url = make_url(raw)
query = dict(url.query)

# Neon often provides psycopg-style URLs:
#   postgresql://...?sslmode=require&channel_binding=require
# asyncpg needs the async driver name and accepts ssl=..., not sslmode/channel_binding.
sslmode = query.pop("sslmode", None)
query.pop("channel_binding", None)
if sslmode and "ssl" not in query:
    query["ssl"] = "require" if sslmode in {"require", "verify-ca", "verify-full"} else sslmode

if url.drivername == "postgresql":
    url = url.set(drivername="postgresql+asyncpg", query=query)
else:
    url = url.set(query=query)

print(url.render_as_string(hide_password=False))
PY
}

PIDS=()

cleanup() {
  trap - INT TERM EXIT
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

require_cmd "$PYTHON_BIN"
require_cmd npm

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  install_deps
fi

if [[ "$RUN_BACKEND" -eq 1 ]]; then
  check_backend_deps
  DATABASE_URL_NORMALIZED="$(normalized_database_url)"
  echo "[backend] http://${HOST}:${BACKEND_PORT}"
  (
    cd "$ROOT_DIR"
    DATABASE_URL="$DATABASE_URL_NORMALIZED" \
      "$PYTHON_BIN" -m uvicorn app.main:app --reload --host "$HOST" --port "$BACKEND_PORT"
  ) &
  PIDS+=("$!")
fi

if [[ "$RUN_FRONTEND" -eq 1 ]]; then
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo "frontend/node_modules is missing. Run: ./run_dev.sh --install" >&2
    exit 1
  fi
  FRONTEND_API_BASE="${VITE_API_BASE:-http://${HOST}:${BACKEND_PORT}}"
  echo "[frontend] http://${HOST}:${FRONTEND_PORT} (VITE_API_BASE=${FRONTEND_API_BASE})"
  (
    cd "$ROOT_DIR/frontend"
    VITE_API_BASE="$FRONTEND_API_BASE" npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
  ) &
  PIDS+=("$!")
fi

echo
echo "Press Ctrl+C to stop."

while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      wait "$pid"
      exit $?
    fi
  done
  sleep 1
done
