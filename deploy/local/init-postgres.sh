#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/deploy/local/.env.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing %s. Copy deploy/local/.env.local.example first.\n' "$ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${POSTGRES_DB:?POSTGRES_DB is required in $ENV_FILE}"
: "${POSTGRES_USER:?POSTGRES_USER is required in $ENV_FILE}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in $ENV_FILE}"

if [[ ! "$POSTGRES_DB" =~ ^[a-z_][a-z0-9_]*$ ]] || [[ ! "$POSTGRES_USER" =~ ^[a-z_][a-z0-9_]*$ ]]; then
  printf 'POSTGRES_DB and POSTGRES_USER must be lowercase PostgreSQL identifiers.\n' >&2
  exit 1
fi

sudo -u postgres psql --set=db_user="$POSTGRES_USER" --set=db_password="$POSTGRES_PASSWORD" --set=db_name="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')\gexec
ALTER ROLE :"db_user" PASSWORD :'db_password';
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')\gexec
SQL

printf 'Local PostgreSQL role and database are ready.\n'
