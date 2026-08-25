#!/usr/bin/env bash
set -Eeuo pipefail

# SQLite plus eager tasks is a disposable browser acceptance environment. It is
# intentionally separate from the native PostgreSQL/Redis local stack in deploy/local.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT_DIR/.venv}"
RUNTIME_DIR="${TRIP_HELPER_DEMO_ROOT:-$ROOT_DIR/.local-web-runtime}"

mkdir -p "$RUNTIME_DIR"
export APP_ENV=development
export APP_NAME="Trip Helper"
export APP_DOMAIN=localhost
export DATABASE_URL="sqlite:///$RUNTIME_DIR/trip-helper.db"
export STORAGE_ROOT="$RUNTIME_DIR/storage"
export TASKS_EAGER=true
export COOKIE_SECURE=false
export SESSION_SECRET="local-browser-test-session-secret"
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

# The A100 image currently ships a native MinerU API on loopback. Use it for
# this disposable local runtime only when its health endpoint is reachable;
# ordinary developer machines continue with the configured Paddle/Tesseract
# chain without waiting for a missing service.
if [[ -z "${OCR_PROVIDER:-}" ]] && command -v curl >/dev/null 2>&1 \
  && curl -fsS --max-time 1 http://127.0.0.1:8888/health >/dev/null 2>&1; then
  export OCR_PROVIDER=mineru
  export MINERU_API_URL=http://127.0.0.1:8888
  export MINERU_ENABLED=true
fi

exec "$VENV_PATH/bin/uvicorn" app.main:app --host 127.0.0.1 --port "${LOCAL_API_PORT:-8001}" --reload
