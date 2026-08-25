#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/deploy/vps/.env}"
INSTALL_OS_DEPS=0
ISSUE_CERTIFICATE=0

usage() {
  cat <<'USAGE'
Usage: sudo deploy/vps/setup-vps.sh [--install-os-deps] [--issue-certificate]

The script publishes already-built React assets, installs Nginx configuration,
and validates Nginx. APP_DOMAIN must resolve to this VPS before requesting a
certificate.
USAGE
}

while (($#)); do
  case "$1" in
    --install-os-deps) INSTALL_OS_DEPS=1 ;;
    --issue-certificate) ISSUE_CERTIFICATE=1 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ "${EUID}" -ne 0 ]]; then
  printf 'Run this setup script as root.\n' >&2
  exit 1
fi

if ((INSTALL_OS_DEPS)); then
  if ! command -v apt-get >/dev/null 2>&1; then
    printf 'Automatic package installation currently targets Debian/Ubuntu.\n' >&2
    exit 1
  fi
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx rsync wireguard-tools
fi

if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0644 "$ROOT_DIR/deploy/vps/.env.example" "$ENV_FILE"
  printf 'Created %s. Set APP_DOMAIN and rerun setup.\n' "$ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${APP_DOMAIN:?APP_DOMAIN is required in $ENV_FILE}"
WEB_ROOT="${WEB_ROOT:-/var/www/trip-helper}"
FRONTEND_DIST="${FRONTEND_DIST:-$ROOT_DIR/frontend/dist}"

if [[ ! "$APP_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  printf 'APP_DOMAIN contains unsupported characters: %s\n' "$APP_DOMAIN" >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_DIST/index.html" ]]; then
  printf 'Expected built frontend at %s. Run npm --prefix frontend run build first.\n' "$FRONTEND_DIST" >&2
  exit 1
fi

install -d -m 0755 "$WEB_ROOT"
rsync -a --delete "$FRONTEND_DIST/" "$WEB_ROOT/"

install -m 0644 "$ROOT_DIR/deploy/vps/nginx/trip-helper-log-format.conf" \
  /etc/nginx/conf.d/trip-helper-log-format.conf

if ((ISSUE_CERTIFICATE)); then
  : "${CERTBOT_EMAIL:?CERTBOT_EMAIL is required when issuing a certificate}"
  rm -f /etc/nginx/sites-enabled/trip-helper.conf
  cat >/etc/nginx/sites-available/trip-helper-bootstrap.conf <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $APP_DOMAIN;
    root $WEB_ROOT;

    location ^~ /.well-known/acme-challenge/ {
        try_files \$uri =404;
    }

    location / {
        return 404;
    }
}
EOF
  ln -sfn /etc/nginx/sites-available/trip-helper-bootstrap.conf /etc/nginx/sites-enabled/trip-helper-bootstrap.conf
  nginx -t
  systemctl reload nginx.service
  certbot certonly --webroot --non-interactive --agree-tos \
    --email "$CERTBOT_EMAIL" -w "$WEB_ROOT" -d "$APP_DOMAIN"
  rm -f /etc/nginx/sites-enabled/trip-helper-bootstrap.conf
  rm -f /etc/nginx/sites-available/trip-helper-bootstrap.conf
fi

sed "s|APP_DOMAIN|$APP_DOMAIN|g" "$ROOT_DIR/deploy/vps/nginx/trip-helper.conf" \
  >/etc/nginx/sites-available/trip-helper.conf
ln -sfn /etc/nginx/sites-available/trip-helper.conf /etc/nginx/sites-enabled/trip-helper.conf

nginx -t
systemctl reload nginx.service

printf 'VPS static frontend and Nginx proxy configuration installed for %s.\n' "$APP_DOMAIN"
