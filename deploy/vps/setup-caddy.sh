#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/deploy/vps/.env}"
INSTALL_OS_DEPS=0

usage() {
  cat <<'USAGE'
Usage: sudo deploy/vps/setup-caddy.sh [--install-os-deps]

Publishes the built React frontend and imports a dedicated Trip Helper site
into an existing Caddyfile. Caddy obtains and renews TLS automatically after
APP_DOMAIN resolves to this VPS.
USAGE
}

while (($#)); do
  case "$1" in
    --install-os-deps) INSTALL_OS_DEPS=1 ;;
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
  command -v apt-get >/dev/null 2>&1 || {
    printf 'Automatic package installation targets Debian/Ubuntu.\n' >&2
    exit 1
  }
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y caddy rsync wireguard-tools
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
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
CADDY_FRAGMENT="${CADDY_FRAGMENT:-/etc/caddy/trip-helper.caddy}"
API_UPSTREAM="${API_UPSTREAM:-10.66.0.2:8000}"

if [[ ! "$APP_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  printf 'APP_DOMAIN contains unsupported characters: %s\n' "$APP_DOMAIN" >&2
  exit 1
fi
if [[ ! "$WEB_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  printf 'WEB_ROOT must be an absolute path without spaces: %s\n' "$WEB_ROOT" >&2
  exit 1
fi
if [[ ! "$API_UPSTREAM" =~ ^[A-Za-z0-9._:-]+$ ]]; then
  printf 'API_UPSTREAM must be a host:port value without spaces: %s\n' "$API_UPSTREAM" >&2
  exit 1
fi
if [[ ! -f "$FRONTEND_DIST/index.html" ]]; then
  printf 'Expected built frontend at %s. Run npm --prefix frontend run build first.\n' "$FRONTEND_DIST" >&2
  exit 1
fi
command -v caddy >/dev/null 2>&1 || {
  printf 'Caddy is not installed. Rerun with --install-os-deps.\n' >&2
  exit 1
}
[[ -f "$CADDYFILE" ]] || {
  printf 'Expected Caddyfile at %s.\n' "$CADDYFILE" >&2
  exit 1
}

install -d -m 0755 "$WEB_ROOT"
rsync -a --delete "$FRONTEND_DIST/" "$WEB_ROOT/"

caddyfile_backup="$(mktemp)"
fragment_backup="$(mktemp)"
had_fragment=0
cp -a "$CADDYFILE" "$caddyfile_backup"
if [[ -f "$CADDY_FRAGMENT" ]]; then
  cp -a "$CADDY_FRAGMENT" "$fragment_backup"
  had_fragment=1
fi

install -d -m 0755 "$(dirname "$CADDY_FRAGMENT")"
sed \
  -e "s|APP_DOMAIN|$APP_DOMAIN|g" \
  -e "s|WEB_ROOT|$WEB_ROOT|g" \
  -e "s|API_UPSTREAM|$API_UPSTREAM|g" \
  "$ROOT_DIR/deploy/vps/caddy/trip-helper.caddy" >"$CADDY_FRAGMENT"
chmod 0644 "$CADDY_FRAGMENT"

import_line="import $CADDY_FRAGMENT"
if ! grep -Fqx "$import_line" "$CADDYFILE"; then
  printf '\n# Trip Helper managed site\n%s\n' "$import_line" >>"$CADDYFILE"
fi

if ! caddy adapt --config "$CADDYFILE" --adapter caddyfile --validate >/dev/null; then
  cp -a "$caddyfile_backup" "$CADDYFILE"
  if ((had_fragment)); then
    cp -a "$fragment_backup" "$CADDY_FRAGMENT"
  else
    rm -f "$CADDY_FRAGMENT"
  fi
  rm -f "$caddyfile_backup" "$fragment_backup"
  printf 'Caddy validation failed; restored the previous configuration.\n' >&2
  exit 1
fi
rm -f "$caddyfile_backup" "$fragment_backup"

systemctl enable --now caddy.service
systemctl reload caddy.service

printf 'Caddy frontend site installed for %s. Configure WireGuard before testing /api/.\n' "$APP_DOMAIN"
