#!/usr/bin/env bash
# Dump FashionRise PostgreSQL database to a gzipped SQL file.
# Usage: bash deploy/backup_postgres.sh
# Requires PGHOST PGPORT PGUSER PGDATABASE PGPASSWORD (or peer auth) in /opt/fashionrise/backend/.env
set -euo pipefail

BACKEND_DIR="${BACKEND_DIR:-/opt/fashionrise/backend}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/fashionrise/backups}"

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "ERROR: $BACKEND_DIR/.env not found"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$BACKEND_DIR/.env"
set +a

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/fashionrise_${STAMP}.sql.gz"

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-fashionrise}"
PGDATABASE="${PGDATABASE:-fashionrise}"

export PGHOST PGPORT PGUSER PGDATABASE

echo "==> Backing up $PGDATABASE on $PGHOST:$PGPORT as $PGUSER -> $OUT"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" | gzip > "$OUT"
echo "OK: $OUT"
