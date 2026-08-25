#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT_DIR/.venv}"
RUNTIME_DIR="${TRIP_HELPER_DEMO_ROOT:-$ROOT_DIR/.local-web-runtime}"

mkdir -p "$RUNTIME_DIR"
export APP_ENV=development
export DATABASE_URL="sqlite:///$RUNTIME_DIR/trip-helper.db"
export STORAGE_ROOT="$RUNTIME_DIR/storage"
export TASKS_EAGER=true
export COOKIE_SECURE=false
export SESSION_SECRET="local-browser-test-session-secret"
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

exec "$VENV_PATH/bin/python" -m app.cli create-admin "$@"
