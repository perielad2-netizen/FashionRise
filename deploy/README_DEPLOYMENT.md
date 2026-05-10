# FashionRise API — production deployment (Ubuntu + Nginx + PostgreSQL)

This guide deploys the **FastAPI** backend from `backend/` on **Ubuntu Linux** with:

- **Python 3** virtual environment  
- **Gunicorn** + **Uvicorn** workers  
- **systemd** service  
- **Nginx** reverse proxy (HTTPS-ready)  
- **PostgreSQL**  
- **Local disk** uploads under `LOCAL_STORAGE_ROOT`  
- Structured **logging** to stdout (journald)

Files in this folder:

| File | Purpose |
|------|---------|
| `README_DEPLOYMENT.md` | This guide |
| `env.production.example` | Template for `/opt/fashionrise/backend/.env` |
| `fashionrise.service` | systemd unit |
| `nginx_fashionrise.conf` | Nginx site (edit `server_name`) |
| `setup_server.sh` | First-time OS packages, user, Postgres, UFW |
| `update_app.sh` | Install deps, Alembic, optional seed, restart app |
| `backup_postgres.sh` | `pg_dump` to gzipped SQL |
| `restore_postgres.sh` | Restore from gzipped SQL |

**Security:** Do not commit `.env`. Use strong `SECRET_KEY`, restrict DB role privileges, enable HTTPS, configure firewall, and set upload limits (Nginx + app).

---

## 1. Install Python, venv, PostgreSQL, Nginx

On a fresh Ubuntu server (22.04 LTS or newer), run the bundled script **as root**:

```bash
sudo bash deploy/setup_server.sh
```

Or manually:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib nginx git ufw
```

---

## 2. Create PostgreSQL database and user

`setup_server.sh` creates role `fashionrise`, database `fashionrise`, and grants. **Change the default password** in the script before running, or after:

```bash
sudo -u postgres psql -c "ALTER ROLE fashionrise PASSWORD 'your_strong_password';"
```

**Least privilege:** The app user should **not** be a PostgreSQL superuser. It only needs `CONNECT`, `CREATE` on schema (if needed), and DML on app tables (migrations run as same user or a dedicated migration user — for simplicity this guide uses one app user).

---

## 3. Clone or copy backend code

Example layout:

```text
/opt/fashionrise/
  backend/          # Git clone or rsync of repo backend/
  deploy/           # copy of deploy/ from repo (or same repo checkout)
```

```bash
sudo mkdir -p /opt/fashionrise
sudo chown fashionrise:fashionrise /opt/fashionrise
sudo -u fashionrise git clone https://github.com/YOUR_ORG/FashionRise.git /opt/fashionrise/src
# or: rsync -a ./backend/ fashionrise@server:/opt/fashionrise/backend/
```

Adjust paths so **`/opt/fashionrise/backend`** contains `app/`, `alembic/`, `requirements.txt`, etc.

---

## 4. Create `.env` file

```bash
sudo -u fashionrise cp /opt/fashionrise/src/deploy/env.production.example /opt/fashionrise/backend/.env
sudo chmod 600 /opt/fashionrise/backend/.env
sudo chown fashionrise:fashionrise /opt/fashionrise/backend/.env
```

Edit `.env`:

- **`DATABASE_URL`** — match PostgreSQL user/password/database.  
- **`SECRET_KEY`** — at least **32** random characters, e.g.  
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`  
- **`CORS_ORIGINS`** — comma-separated **HTTPS** origins for your frontends (**no** `*` in production; the app enforces this when `ENVIRONMENT=production`).  
- **`LOCAL_STORAGE_ROOT`** — e.g. `/var/lib/fashionrise/storage`  
- **`PUBLIC_UPLOAD_BASE_URL`** — public URL prefix for files, e.g. `https://api.example.com/static/uploads`  
- **`PGHOST` / `PGPORT` / `PGUSER` / `PGDATABASE` / `PGPASSWORD`** — for backup/restore scripts (`pg_dump` / `psql`).

---

## 5. Install Python dependencies

```bash
sudo -u fashionrise python3 -m venv /opt/fashionrise/backend/.venv
sudo -u fashionrise /opt/fashionrise/backend/.venv/bin/pip install --upgrade pip wheel
sudo -u fashionrise /opt/fashionrise/backend/.venv/bin/pip install -r /opt/fashionrise/backend/requirements.txt
```

---

## 6. Run Alembic migrations

```bash
cd /opt/fashionrise/backend
sudo -u fashionrise bash -lc 'source .venv/bin/activate && alembic upgrade head'
```

---

## 7. Seed initial catalog (materials, templates, palettes)

The HTTP app **does not** auto-seed on startup when `ENVIRONMENT=production`. Run the idempotent seed **once** (or after you need fresh catalog rows):

```bash
cd /opt/fashionrise/backend
sudo -u fashionrise bash -lc 'source .venv/bin/activate && python -m app.seed'
```

**Note:** `run_seed_if_configured()` only runs automatically in **development**; production relies on this explicit `python -m app.seed` step (or `RUN_SEED=1` with `update_app.sh`).

---

## 8. Configure systemd service

```bash
sudo cp deploy/fashionrise.service /etc/systemd/system/fashionrise.service
# Edit paths/user if you did not use /opt/fashionrise/backend or user fashionrise
sudo systemctl daemon-reload
sudo systemctl enable fashionrise
```

Ensure `.env` exists and is readable by `fashionrise`.

---

## 9. Configure Nginx reverse proxy

```bash
sudo cp deploy/nginx_fashionrise.conf /etc/nginx/sites-available/fashionrise
sudo nano /etc/nginx/sites-available/fashionrise   # set server_name
sudo ln -sf /etc/nginx/sites-available/fashionrise /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Upload size:** `client_max_body_size` should exceed **`MAX_UPLOAD_SIZE_MB`** in `.env` (e.g. 30M vs 25 MB app limit).

---

## 10. SSL with Certbot (Let’s Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com
```

Certbot will add a `listen 443 ssl` server block. Ensure **`client_max_body_size`** and **`proxy_pass`** settings are present in the **443** server (copy from port 80 block if Certbot’s snippet is minimal).

---

## 11. Uploads folder permissions

```bash
sudo mkdir -p /var/lib/fashionrise/storage/uploads
sudo chown -R fashionrise:fashionrise /var/lib/fashionrise/storage
sudo chmod 750 /var/lib/fashionrise/storage
```

If Nginx serves `/static/uploads/` **directly** from disk, either:

- Grant read access to `www-data` (e.g. ACL: `sudo setfacl -R -m g:www-data:rX /var/lib/fashionrise/storage/uploads`), **or**  
- Proxy all `/static/uploads` through the app (simpler permissions; default app behavior).

---

## 12. Restart services

```bash
sudo systemctl restart fashionrise
sudo systemctl reload nginx
```

---

## 13. Test health endpoint

```bash
curl -sS http://127.0.0.1:8000/health
# {"status":"ok"}

curl -sS http://127.0.0.1:8000/ready
# {"status":"ready","database":"ok"}
```

Through Nginx (HTTP or HTTPS):

```bash
curl -sS https://api.example.com/health
```

---

## 14. Test OpenAPI docs

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs
# 200
```

Open in browser: `https://api.example.com/docs` (disable in production behind auth if desired — future hardening).

---

## 15. Backup and restore PostgreSQL

**Backup** (cron-friendly):

```bash
sudo chmod +x deploy/backup_postgres.sh
# Ensure .env contains PG* vars and PGPASSWORD if not using peer auth
sudo -u fashionrise bash deploy/backup_postgres.sh
```

**Restore** (destructive — test on staging first):

```bash
sudo chmod +x deploy/restore_postgres.sh
sudo -u fashionrise bash deploy/restore_postgres.sh /var/lib/fashionrise/backups/fashionrise_YYYYMMDD_HHMMSS.sql.gz
```

---

## 16. Update deployment workflow

After code changes:

```bash
# On server, as user with sudo
sudo -u fashionrise git -C /opt/fashionrise/src pull
sudo rsync -a --delete /opt/fashionrise/src/backend/ /opt/fashionrise/backend/   # if you split repo
sudo -u fashionrise bash /opt/fashionrise/src/deploy/update_app.sh
```

Or copy `update_app.sh` next to the backend and set `BACKEND_DIR`. Optional one-time seed after schema change:

```bash
sudo -u fashionrise RUN_SEED=1 bash deploy/update_app.sh
```

(`RUN_SEED=1` runs `python -m app.seed` — use with care in production.)

---

## Application behavior (production)

| Topic | Behavior |
|--------|----------|
| **Logging** | `LOG_LEVEL`; structured lines to stdout (journalctl for systemd service) |
| **CORS** | `CORS_ORIGINS` must be explicit when `ENVIRONMENT=production` |
| **Uploads** | Max size `MAX_UPLOAD_SIZE_MB`; content-types `ALLOWED_UPLOAD_IMAGE_TYPES`; JPEG/PNG/WebP magic-byte check |
| **Health** | `GET /health` liveness; `GET /ready` checks DB |
| **Secrets** | `SECRET_KEY` length and `DEBUG=false` enforced for `production` |

---

## Firewall

`setup_server.sh` enables UFW with **OpenSSH** and **Nginx Full**. Adjust for your SSH port and policies.

---

## Troubleshooting

- **`systemctl status fashionrise`** — failed start: check `journalctl -u fashionrise -e`.  
- **502 from Nginx** — app not listening on `127.0.0.1:8000`; check Gunicorn bind.  
- **413** on upload — raise Nginx `client_max_body_size` and `MAX_UPLOAD_SIZE_MB`.  
- **CORS errors** — set exact browser origin in `CORS_ORIGINS` (scheme + host + port).
