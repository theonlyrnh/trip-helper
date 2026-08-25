#!/usr/bin/env bash
set -Eeuo pipefail

: "${OCR_SERVER_COMMAND:?Set OCR_SERVER_COMMAND in /etc/trip-helper/trip-helper.env before enabling this service}"

# The environment file is root-owned and only writable by trusted operators.
# The configured command must bind to 127.0.0.1:8118, never a public address.
exec /bin/sh -c "$OCR_SERVER_COMMAND"
