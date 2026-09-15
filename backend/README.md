# FashionRise — FastAPI backend

Production-minded API for **Ubuntu + Nginx + PostgreSQL**: JWT auth, SQLAlchemy 2.x, Alembic, local file storage with a **swappable storage interface** for S3-compatible backends later.

**Repo:** clone [FashionRise](https://github.com/perielad2-netizen/FashionRise) and work in this `backend/` folder. Do **not** commit `.env` (use `.env.example`). Session handoff: `docs/00-PROJECT-STATUS.md`.

## Requirements

- Python **3.11+**
- **PostgreSQL** 14+ (JSONB)

## Setup

```bash
cd backend
python -m venv .venv
```

**Windows (PowerShell):** `.venv\Scripts\Activate.ps1`  
**Linux/macOS:** `source .venv/bin/activate`

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set SECRET_KEY, DATABASE_URL, CORS_ORIGINS, etc.
```

### PostgreSQL

Create role and database (example):

```sql
CREATE USER fashionrise WITH PASSWORD 'fashionrise';
CREATE DATABASE fashionrise OWNER fashionrise;
```

Match `DATABASE_URL` in `.env`, e.g.:

`postgresql+psycopg2://fashionrise:fashionrise@localhost:5432/fashionrise`

### Migrations

From `backend/` (with venv active):

```bash
alembic upgrade head
```

**Settings:** the API and Alembic both read **`backend/.env`** via an **absolute path** in `app/core/config.py` — you get the same `DATABASE_URL` whether you run commands from `backend/` or the repo root.

**Recovery** (dev): if `alembic current` shows `003` but the app says tables like `material_definitions` / `ai_jobs` are missing, your `alembic_version` row is ahead of the real schema. From `backend/` run:

```bash
alembic downgrade base
alembic upgrade head
```

That reapplies **`001`–`003`** (downgrades use `IF EXISTS` drops so a broken partial DB can still be unwound). **This deletes application data** in that Postgres database.

Create a new revision after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Run (development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

- OpenAPI UI: http://localhost:8001/docs  
- Health: `GET /health`  
- Readiness (DB ping): `GET /ready`

SQL statement logging is **off** by default. To trace queries, set **`SQLALCHEMY_ECHO=true`** in `.env` (very noisy while the in-process AI worker is polling).

### AI job worker (optional, split deployments)

By default the API process runs a small in-process loop that drains **`queued`** rows in **`ai_jobs`**. If you run **multiple API replicas**, set **`AI_WORKER_ENABLED=false`** in `.env` on each API instance and run a dedicated worker from `backend/`:

```bash
python -m app.ai_worker
```

Single batch (e.g. cron smoke): `python -m app.ai_worker --once`. Poll interval and batch size use the same **`AI_WORKER_*`** variables as the embedded loop.

### Catalog seed

In **`ENVIRONMENT=development`**, startup runs an **idempotent** seed for materials, garment templates, and color palettes (skipped when `TESTING=true` or non-development).

## Layout

- `app/main.py` — app factory, CORS, static uploads mount, lifespan  
- `app/core/` — settings, security (JWT, passwords), errors  
- `app/db/` — engine, session, `Base`  
- `app/models/` — SQLAlchemy models  
- `app/schemas/` — Pydantic v2 I/O models  
- `app/services/` — business logic  
- `app/repositories/` — reserved for heavier queries  
- `app/api/v1/routes/` — HTTP routers  
- `app/storage/` — `StorageBackend` protocol + `LocalStorageBackend`  
- `app/ai/` — placeholder boundary (jobs implemented in `services/ai_service.py`)  
- `alembic/` — migrations  

## API prefix

All versioned routes are under **`/api/v1`** (e.g. `POST /api/v1/auth/login`).

## Uploads & static files

- Files are stored under `LOCAL_STORAGE_ROOT` / `UPLOAD_SUBDIR` (default `./data/storage/uploads`).  
- Served at **`/static/uploads/...`** (align `PUBLIC_UPLOAD_BASE_URL` with your public origin).  
- Replace `LocalStorageBackend` with an S3 implementation of `StorageBackend` when ready.

## Tests

```bash
pytest
```

Default tests avoid DB seed (`TESTING=true` in `tests/conftest.py`). Add integration tests with a real `DATABASE_URL` as needed.

## Production deployment

See **`../deploy/README_DEPLOYMENT.md`** for Ubuntu, systemd, Nginx, PostgreSQL backups, and `env.production.example`.

## Security notes

- Change **`SECRET_KEY`** and use strong DB credentials in production.  
- Set **`ENVIRONMENT=production`**, **`DEBUG=false`**, restrict **`CORS_ORIGINS`** (wildcard `*` is rejected for production).  
- Image uploads: **`MAX_UPLOAD_SIZE_MB`**, allowed MIME types, and magic-byte checks (JPEG/PNG/WebP).  
- Refresh tokens are stored **hashed**; rotation happens on `/auth/refresh`.
- **HTTP rate limits** (SlowAPI, per IP from `X-Forwarded-For` or direct client): `POST /auth/login` 30/min, `/auth/register` 20/min, `/auth/refresh` and `/auth/logout` 60/min, `POST /uploads/image` 40/min; **`POST /ai/sketch/*`**, **`POST /ai/style/suggest`**, **`POST /ai/jobs`** 40/min each; **`GET /ai/jobs/{id}`** 400/min (client polling). Configure Nginx to set **`X-Forwarded-For`** so limits apply per end user, not per proxy hop. (SlowAPI response header injection is disabled so JSON routes do not 500.)

## Dev utilities

- **Reset a user password** (bcrypt, same as `POST /auth/register`): from `backend/` with venv active, run  
  `python scripts/set_user_password.py you@example.com "NewPassword123"`  
  Use if the account was inserted manually / password unknown — **`401` on login with `409` on re-register means the email exists but the password does not match the stored hash.**
