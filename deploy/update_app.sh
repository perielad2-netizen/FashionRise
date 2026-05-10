#!/usr/bin/env bash
# FashionRise — deploy / update application (run as app user, not root).
# Usage:
#   sudo -u fashionrise bash deploy/update_app.sh
#   BACKEND_DIR=/opt/fashionrise/backend sudo -u fashionrise bash deploy/update_app.sh
set -euo pipefail

BACKEND_DIR="${BACKEND_DIR:-/opt/fashionrise/backend}"
VENV="$BACKEND_DIR/.venv"

cd "$BACKEND_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: $BACKEND_DIR/.env missing. Copy deploy/env.production.example and configure."
  exit 1
fi

echo "==> Python venv..."
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install --upgrade pip wheel
pip install -r requirements.txt

echo "==> Alembic migrations..."
alembic upgrade head

if [[ "${RUN_SEED:-0}" == "1" ]]; then
  echo "==> Catalog seed (RUN_SEED=1)..."
  python -m app.seed
fi

deactivate

if [[ "${SKIP_SYSTEMD_RESTART:-0}" != "1" ]] && command -v systemctl &>/dev/null; then
  echo "==> Restarting fashionrise.service (requires sudo if not root)..."
  sudo systemctl restart fashionrise || systemctl restart fashionrise
fi

echo "==> Done. Check: curl -sS http://127.0.0.1:8000/health"
