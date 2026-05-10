# FashionRise — FastAPI backend

Production-minded API for **Ubuntu + Nginx + PostgreSQL**: JWT auth, SQLAlchemy 2.x, Alembic, local file storage with a **swappable storage interface** for S3-compatible backends later.

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

Create a new revision after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Run (development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI UI: http://localhost:8000/docs  
- Health: `GET /health`  
- Readiness (DB ping): `GET /ready`

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
