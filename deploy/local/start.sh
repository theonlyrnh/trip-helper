#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/deploy/local/.env.local}"
VENV_PATH="${VENV_PATH:-$ROOT_DIR/.venv}"
COMMAND="${1:-help}"

usage() {
  cat <<'USAGE'
Usage: deploy/local/start.sh <bootstrap|api|worker-cpu|worker-gpu|frontend|check>

Each long-running command occupies the current terminal. Start api,
worker-cpu, and frontend in separate terminals. worker-gpu requires an NVIDIA
driver and remains single-concurrency.
USAGE
}

load_environment() {
  if [[ ! -f "$ENV_FILE" ]]; then
    printf 'Missing %s. Copy deploy/local/.env.local.example first.\n' "$ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  if [[ "$VENV_PATH" != /* ]]; then
    VENV_PATH="$ROOT_DIR/$VENV_PATH"
  fi

  # Prefer the native A100 MinerU service when it is already running. This is
  # a local convenience probe; it does not make MinerU a requirement for
  # ordinary machines that use Tesseract as the fallback.
  if [[ "${OCR_PROVIDER:-local_paddle}" != "tesseract" \
    && "${OCR_PROVIDER:-local_paddle}" != "local_tesseract" ]] \
    && command -v curl >/dev/null 2>&1 \
    && curl -fsS --max-time 1 http://127.0.0.1:8888/health >/dev/null 2>&1; then
    export OCR_PROVIDER=mineru
    export MINERU_API_URL=http://127.0.0.1:8888
    export MINERU_ENABLED=true
  fi
}

bootstrap() {
  python3 -m venv "$VENV_PATH"
  "$VENV_PATH/bin/pip" install --upgrade pip wheel
  if [[ -f "$ROOT_DIR/backend/pyproject.toml" ]]; then
    "$VENV_PATH/bin/pip" install --editable "$ROOT_DIR/backend"
  else
    "$VENV_PATH/bin/pip" install --requirement "$ROOT_DIR/backend/requirements.txt"
  fi
}

check_services() {
  pg_isready -h 127.0.0.1 -d "${POSTGRES_DB:?POSTGRES_DB is required}" -U "${POSTGRES_USER:?POSTGRES_USER is required}" >/dev/null
  redis-cli -h 127.0.0.1 ping | grep -qx PONG
}

run_api() {
  exec "$VENV_PATH/bin/uvicorn" app.main:app \
    --app-dir "$ROOT_DIR/backend" \
    --host "${LOCAL_API_HOST:-127.0.0.1}" \
    --port "${LOCAL_API_PORT:-8000}" \
    --reload
}

run_worker_cpu() {
  cd "$ROOT_DIR/backend"
  exec "$VENV_PATH/bin/celery" -A app.workers.celery_app worker \
    -Q cpu,default --concurrency=2 --loglevel=INFO
}

run_worker_gpu() {
  nvidia-smi >/dev/null
  cd "$ROOT_DIR/backend"
  exec "$VENV_PATH/bin/celery" -A app.workers.celery_app worker \
    -Q gpu --concurrency=1 --loglevel=INFO
}

case "$COMMAND" in
  help|-h|--help)
    usage
    exit 0
    ;;
esac

load_environment

case "$COMMAND" in
  bootstrap) bootstrap ;;
  check) check_services ;;
  api) check_services; run_api ;;
  worker-cpu) check_services; run_worker_cpu ;;
  worker-gpu) check_services; run_worker_gpu ;;
  frontend) exec npm --prefix "$ROOT_DIR/frontend" run dev ;;
  *) printf 'Unknown command: %s\n' "$COMMAND" >&2; usage >&2; exit 2 ;;
esac
