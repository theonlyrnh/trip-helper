#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/opt/trip-helper}"
APP_USER="${APP_USER:-trip-helper}"
APP_GROUP="${APP_GROUP:-trip-helper}"
VENV_PATH="${VENV_PATH:-$APP_ROOT/.venv}"
ENV_FILE="${ENV_FILE:-/etc/trip-helper/trip-helper.env}"
DATA_ROOT_DEFAULT="${DATA_ROOT_DEFAULT:-/srv/trip-helper}"
INSTALL_OS_DEPS=0
ENABLE_OCR=0

usage() {
  cat <<'USAGE'
Usage: sudo deploy/a100/setup-a100.sh [--install-os-deps] [--enable-ocr]

The script provisions the native A100 runtime, PostgreSQL role/database,
Python virtual environment, and systemd unit files. Before the first run,
copy deploy/a100/.env.production.example to /etc/trip-helper/trip-helper.env
and replace its placeholders.
USAGE
}

while (($#)); do
  case "$1" in
    --install-os-deps) INSTALL_OS_DEPS=1 ;;
    --enable-ocr) ENABLE_OCR=1 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    printf 'Run this setup script as root.\n' >&2
    exit 1
  fi
}

require_systemd_host() {
  local init_name
  init_name="$(ps -p 1 -o comm= 2>/dev/null | tr -d '[:space:]')"
  if [[ "$init_name" != "systemd" ]]; then
    printf '%s\n' 'This installer manages native systemd services and must run on the A100 host where PID 1 is systemd.' >&2
    printf '%s\n' 'Enter the A100 host or its privileged service namespace before running this installer.' >&2
    exit 1
  fi
  systemctl show-environment >/dev/null 2>&1 || {
    printf '%s\n' 'systemd is not reachable from this shell.' >&2
    exit 1
  }
}

require_wireguard_address() {
  command -v ip >/dev/null 2>&1 || {
    printf '%s\n' 'iproute2 is required to verify the WireGuard interface.' >&2
    exit 1
  }
  ip -o -4 addr show dev wg0 2>/dev/null | grep -qE '[[:space:]]inet[[:space:]]+10\.66\.0\.2/' || {
    printf '%s\n' 'WireGuard interface wg0 with address 10.66.0.2 is required before installing the private API.' >&2
    exit 1
  }
}

install_os_dependencies() {
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential libpq-dev postgresql postgresql-client \
      python3 python3-dev python3-pip python3-venv redis-server \
      wireguard-tools tesseract-ocr tesseract-ocr-chi-sim
    return
  fi

  printf '%s\n' 'Automatic package installation currently targets Debian/Ubuntu.' >&2
  printf '%s\n' 'Install Python 3.11+, PostgreSQL, Redis, WireGuard tools, compiler headers, and NVIDIA drivers manually, then rerun without --install-os-deps.' >&2
  exit 1
}

validate_identifier() {
  local value="$1"
  local label="$2"
  if [[ ! "$value" =~ ^[a-z_][a-z0-9_]*$ ]]; then
    printf '%s must be a lowercase PostgreSQL identifier: %s\n' "$label" "$value" >&2
    exit 1
  fi
}

load_environment() {
  if [[ ! -f "$ENV_FILE" ]]; then
    install -d -m 0750 -o root -g "$APP_GROUP" /etc/trip-helper
    install -m 0640 -o root -g "$APP_GROUP" \
      "$APP_ROOT/deploy/a100/.env.production.example" "$ENV_FILE"
    printf 'Created %s. Replace all placeholders and rerun setup.\n' "$ENV_FILE" >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  : "${POSTGRES_DB:?POSTGRES_DB is required in $ENV_FILE}"
  : "${POSTGRES_USER:?POSTGRES_USER is required in $ENV_FILE}"
  : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in $ENV_FILE}"
  : "${DATABASE_URL:?DATABASE_URL is required in $ENV_FILE}"
  : "${SESSION_SECRET:?SESSION_SECRET is required in $ENV_FILE}"
  DATA_ROOT="${DATA_ROOT:-$DATA_ROOT_DEFAULT}"
  validate_identifier "$POSTGRES_DB" POSTGRES_DB
  validate_identifier "$POSTGRES_USER" POSTGRES_USER
}

ensure_service_identity() {
  if ! getent group "$APP_GROUP" >/dev/null; then
    groupadd --system "$APP_GROUP"
  fi
  if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --gid "$APP_GROUP" --home-dir /nonexistent --shell /usr/sbin/nologin "$APP_USER"
  fi
}

provision_user_and_directories() {
  ensure_service_identity

  install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" \
    "$DATA_ROOT" "$DATA_ROOT/cache" "$DATA_ROOT/exports" \
    "$DATA_ROOT/originals" "$DATA_ROOT/previews" "$DATA_ROOT/tmp"
  install -d -m 0750 -o root -g "$APP_GROUP" /etc/trip-helper
  chown root:"$APP_GROUP" "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
}

provision_python() {
  python3 -m venv "$VENV_PATH"
  "$VENV_PATH/bin/pip" install --upgrade pip wheel

  if [[ -f "$APP_ROOT/backend/pyproject.toml" ]]; then
    "$VENV_PATH/bin/pip" install --editable "$APP_ROOT/backend"
  else
    "$VENV_PATH/bin/pip" install --requirement "$APP_ROOT/backend/requirements.txt"
  fi

  chown -R "$APP_USER":"$APP_GROUP" "$VENV_PATH"
}

provision_postgres() {
  systemctl enable --now postgresql.service

  runuser -u postgres -- psql --set=db_user="$POSTGRES_USER" --set=db_password="$POSTGRES_PASSWORD" --set=db_name="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')\gexec
ALTER ROLE :"db_user" PASSWORD :'db_password';
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')\gexec
ALTER SYSTEM SET listen_addresses = '127.0.0.1';
SQL

  systemctl restart postgresql.service
}

provision_redis() {
  local redis_config=/etc/redis/redis.conf
  if [[ ! -f "$redis_config" ]]; then
    printf 'Expected Redis configuration at %s.\n' "$redis_config" >&2
    exit 1
  fi
  if grep -qE '^[[:space:]]*bind[[:space:]]+' "$redis_config"; then
    sed -i -E 's|^[[:space:]]*bind[[:space:]].*$|bind 127.0.0.1 ::1|' "$redis_config"
  else
    printf '\nbind 127.0.0.1 ::1\n' >>"$redis_config"
  fi
  if grep -qE '^[[:space:]]*protected-mode[[:space:]]+' "$redis_config"; then
    sed -i -E 's|^[[:space:]]*protected-mode[[:space:]].*$|protected-mode yes|' "$redis_config"
  else
    printf 'protected-mode yes\n' >>"$redis_config"
  fi
  systemctl enable --now redis-server.service
  systemctl restart redis-server.service
  redis-cli -h 127.0.0.1 ping | grep -qx PONG
}

verify_gpu() {
  command -v nvidia-smi >/dev/null 2>&1
  nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
}

run_migrations() {
  if [[ ! -f "$APP_ROOT/backend/alembic.ini" ]]; then
    printf 'Expected Alembic configuration at %s/backend/alembic.ini.\n' "$APP_ROOT" >&2
    exit 1
  fi

  runuser -u "$APP_USER" -- /bin/sh -c \
    '. "$1"; exec "$2" -c "$3" upgrade head' \
    sh "$ENV_FILE" "$VENV_PATH/bin/alembic" "$APP_ROOT/backend/alembic.ini"
}

render_unit() {
  local template="$1"
  local output="/etc/systemd/system/${template}"
  sed \
    -e "s|__APP_ROOT__|$APP_ROOT|g" \
    -e "s|__APP_USER__|$APP_USER|g" \
    -e "s|__APP_GROUP__|$APP_GROUP|g" \
    -e "s|__VENV_PATH__|$VENV_PATH|g" \
    -e "s|__ENV_FILE__|$ENV_FILE|g" \
    -e "s|__DATA_ROOT__|$DATA_ROOT|g" \
    "$APP_ROOT/deploy/a100/systemd/${template}" >"$output"
  chmod 0644 "$output"
}

install_systemd_units() {
  render_unit trip-helper-api.service
  render_unit trip-helper-worker-cpu.service
  render_unit trip-helper-worker-gpu.service
  render_unit trip-helper-ocr.service
  install -d -m 0755 /usr/local/libexec
  install -m 0755 "$APP_ROOT/deploy/a100/run-ocr-service.sh" /usr/local/libexec/trip-helper-ocr
  systemctl daemon-reload
  systemctl enable trip-helper-api.service trip-helper-worker-cpu.service trip-helper-worker-gpu.service
  if ((ENABLE_OCR)); then
    : "${OCR_SERVER_COMMAND:?Set OCR_SERVER_COMMAND before enabling OCR}"
    systemctl enable trip-helper-ocr.service
  fi
  systemctl restart trip-helper-api.service trip-helper-worker-cpu.service trip-helper-worker-gpu.service
  if ((ENABLE_OCR)); then
    systemctl restart trip-helper-ocr.service
  fi
}

require_root
[[ -d "$APP_ROOT/backend" ]] || { printf 'APP_ROOT must contain backend/: %s\n' "$APP_ROOT" >&2; exit 1; }
require_systemd_host

if ((INSTALL_OS_DEPS)); then
  install_os_dependencies
fi

ensure_service_identity
load_environment
require_wireguard_address
provision_user_and_directories
provision_python
provision_postgres
provision_redis
verify_gpu
run_migrations
install_systemd_units

printf 'A100 native services installed. Verify with systemctl status trip-helper-api trip-helper-worker-cpu trip-helper-worker-gpu.\n'
