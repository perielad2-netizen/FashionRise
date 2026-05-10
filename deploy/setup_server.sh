#!/usr/bin/env bash
# FashionRise — first-time Ubuntu server setup (run with sudo or as root).
# Usage: sudo bash deploy/setup_server.sh
set -euo pipefail

APP_USER="${APP_USER:-fashionrise}"
APP_GROUP="${APP_GROUP:-fashionrise}"
APP_ROOT="${APP_ROOT:-/opt/fashionrise}"
BACKEND_DIR="${BACKEND_DIR:-$APP_ROOT/backend}"
STORAGE_ROOT="${STORAGE_ROOT:-/var/lib/fashionrise/storage}"

echo "==> Updating apt and installing packages..."
apt-get update -y
apt-get install -y \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  git \
  ufw \
  acl

echo "==> Creating system user $APP_USER..."
if ! id "$APP_USER" &>/dev/null; then
  useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$APP_USER"
fi

mkdir -p "$APP_ROOT" "$BACKEND_DIR" "$STORAGE_ROOT/uploads"
chown -R "$APP_USER:$APP_GROUP" "$APP_ROOT" "$STORAGE_ROOT"

echo "==> PostgreSQL: create role and database (change default password in script or edit role after)..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$APP_USER') THEN
    CREATE ROLE $APP_USER WITH LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
  END IF;
END
\$\$;
SQL

DB_EXISTS="$(sudo -u postgres psql -Atqc "SELECT 1 FROM pg_database WHERE datname='fashionrise'")"
if [[ "${DB_EXISTS:-}" != "1" ]]; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE fashionrise OWNER $APP_USER;"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE fashionrise TO $APP_USER;"

echo "==> Grant schema usage for app user (connect to fashionrise DB)..."
sudo -u postgres psql -v ON_ERROR_STOP=1 -d fashionrise <<SQL
GRANT ALL ON SCHEMA public TO $APP_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $APP_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $APP_USER;
SQL

echo "==> Firewall (UFW): allow SSH, HTTP, HTTPS..."
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
ufw --force enable || true

echo "==> Install systemd unit..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 644 "$SCRIPT_DIR/fashionrise.service" /etc/systemd/system/fashionrise.service
systemctl daemon-reload

echo ""
echo "Next steps (as $APP_USER or deploy user):"
echo "  1. Clone or rsync backend code to $BACKEND_DIR"
echo "  2. Copy deploy/env.production.example to $BACKEND_DIR/.env and edit (chmod 600)"
echo "  3. Match DATABASE_URL password with PostgreSQL role password"
echo "  4. Run: sudo -u $APP_USER bash deploy/update_app.sh  (from repo root, or copy script)"
echo "  5. sudo systemctl enable --now fashionrise"
echo "  6. Configure Nginx from deploy/nginx_fashionrise.conf"
echo "  7. curl -sS http://127.0.0.1:8000/health && curl -sS http://127.0.0.1:8000/ready"
