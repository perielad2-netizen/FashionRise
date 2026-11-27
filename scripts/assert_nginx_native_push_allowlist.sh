#!/usr/bin/env bash
# Assert production-style nginx conf contains native push device allowlist.
# Usage:
#   scripts/assert_nginx_native_push_allowlist.sh [path-to-nginx-conf]
# Exit 0 on pass, 1 on fail.
set -euo pipefail

CONF="${1:-}"
if [[ -z "$CONF" ]]; then
  if [[ -f /etc/nginx/sites-available/fashionrise.app ]]; then
    CONF=/etc/nginx/sites-available/fashionrise.app
  else
    CONF="$(cd "$(dirname "$0")/.." && pwd)/deploy/nginx-allowlists/native-push.conf.snippet"
  fi
fi

if [[ ! -f "$CONF" ]]; then
  echo "FAIL: conf not found: $CONF" >&2
  exit 1
fi

fail=0
require() {
  local pat="$1"
  local label="$2"
  if ! grep -qE "$pat" "$CONF"; then
    echo "FAIL: missing $label ($pat) in $CONF" >&2
    fail=1
  else
    echo "OK: $label"
  fi
}

require 'location = /api/v1/push/native/capability' 'capability location'
require 'location = /api/v1/push/native/devices' 'devices location'
require 'limit_except GET POST DELETE OPTIONS' 'devices methods (GET POST DELETE OPTIONS)'
# Ensure we are not opening a whole /push/ prefix
if grep -qE 'location[[:space:]]+/api/v1/push/' "$CONF"; then
  echo "FAIL: broad /api/v1/push/ prefix allowlist is not permitted" >&2
  fail=1
else
  echo "OK: no broad /api/v1/push/ prefix"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "PASS: native push nginx allowlist present in $CONF"
