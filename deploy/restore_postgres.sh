#!/usr/bin/env bash
# Restore FashionRise DB from a gzipped pg_dump (plain SQL).
# Usage: bash deploy/restore_postgres.sh /var/lib/fashionrise/backups/fashionrise_YYYYMMDD_HHMMSS.sql.gz
# WARNING: This will drop and recreate objects depending on dump content; test on a staging DB first.
set -euo pipefail

BACKEND_DIR="${BACKEND_DIR:-/opt/fashionrise/backend}"
DUMP="$1"

if [[ -z "${DUMP:-}" || ! -f "$DUMP" ]]; then
  echo "Usage: $0 /path/to/fashionrise_*.sql.gz"
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "ERROR: $BACKEND_DIR/.env not found"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$BACKEND_DIR/.env"
set +a

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-fashionrise}"
PGDATABASE="${PGDATABASE:-fashionrise}"
export PGHOST PGPORT PGUSER PGDATABASE

echo "==> Restoring $DUMP into $PGDATABASE on $PGHOST (user $PGUSER)"
read -r -p "Type the database name to confirm: " confirm
if [[ "$confirm" != "$PGDATABASE" ]]; then
  echo "Aborted."
  exit 1
fi

# Stop app to avoid connections during restore (optional but safer)
if systemctl is-active --quiet fashionrise 2>/dev/null; then
  sudo systemctl stop fashionrise
  trap 'sudo systemctl start fashionrise' EXIT
fi

gunzip -c "$DUMP" | psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -v ON_ERROR_STOP=1 -d "$PGDATABASE"
echo "OK: restore finished. Start fashionrise if it was stopped."
