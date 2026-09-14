# FashionRise — Backend architecture (FastAPI)

**Code root:** `backend/` (not a separate `fashionrise-backend/` repo path).

## Layout (as implemented)

```text
backend/
  app/
    main.py              # create_app(), logging, CORS, /health, /ready, static mount, lifespan (seed, schema probe, optional AI worker)
    seed.py              # Idempotent catalog seed; python -m app.seed for one-off runs
    core/
      config.py          # Pydantic Settings; production safety checks
      security.py        # JWT, password hashing
      errors.py          # AppError + handlers
      logging_config.py  # stdout logging (LOG_LEVEL)
      upload_validation.py  # Image size / MIME / magic-byte checks
      rate_limit.py        # SlowAPI limiter (see README security notes)
    api/
      v1/
        router.py        # include_router * /api/v1
        routes/          # auth, profiles, designs, materials, templates, palettes,
                         # gallery, ratings, exports, uploads, ai_routes
    models/              # SQLAlchemy 2.x ORM
    schemas/             # Pydantic v2 I/O
    services/            # Business logic
    repositories/        # Present; heavier queries can move here
    db/
      session.py         # Engine, SessionLocal, get_db
      base.py            # DeclarativeBase, import_models for Alembic
    auth/
      dependencies.py    # CurrentUser, etc.
    storage/
      base.py            # Protocol / abstraction
      local.py           # Local disk backend
    ai/
      service.py         # Boundary placeholder
  alembic/
    env.py
    versions/
  tests/
  requirements.txt
  README.md
```

## Runtime stack

- **Development:** `uvicorn app.main:app --reload`
- **Production:** **Gunicorn** + **UvicornWorker** (see `deploy/fashionrise.service`)
- **PostgreSQL** + **SQLAlchemy 2.x** + **Alembic**
- **Nginx:** TLS, reverse proxy, `client_max_body_size` — see `deploy/nginx_fashionrise.conf` and `deploy/README_DEPLOYMENT.md`

## Module responsibilities

| Area | Responsibility |
|------|----------------|
| `app/core/config.py` | Env-based settings; loads **`backend/.env`** by absolute path (not cwd-relative); **production** forbids weak `SECRET_KEY`, `CORS=*`, `DEBUG=true` (unless `TESTING=true`) |
| `app/core/logging_config.py` | Root logger for app + workers |
| `app/core/upload_validation.py` | Stream read cap; JPEG/PNG/WebP sniff |
| `app/auth/` | JWT access; refresh tokens hashed in DB |
| `app/storage/` | Local files; S3-compatible driver later |
| `app/services/` | Transactions, rules; **`auth_service`** normalizes email (lowercase), case-insensitive login lookup, trims passwords for hash/verify |
| `app/ai/` | Job boundary; real workers TBD |

## Database & migrations (dev recovery)

- **Alembic** uses the same **`DATABASE_URL`** as the API (`get_settings().database_url`).
- If **`alembic current`** shows **`003`** but tables are missing (e.g. empty DB stamped manually), run from **`backend/`**: **`alembic downgrade base`** then **`alembic upgrade head`**. Downgrades on revisions **`001`–`003`** use **`if_exists=True`** on `DROP INDEX` / `DROP TABLE` so partial schemas do not block recovery (**this wipes app tables** in that database).
- **Lifespan:** dev catalog **seed** catches missing-table errors and logs a warning; a **schema probe** logs if `material_definitions` is absent; the in-process **AI worker** stops after the first schema `ProgrammingError` until process restart (avoids log spam).

## OpenAPI

- **`/docs`** — Swagger UI (control exposure in production as needed).

## Security & ops (implemented)

- **`GET /health`** — liveness  
- **`GET /ready`** — DB connectivity  
- **Uploads:** `MAX_UPLOAD_SIZE_MB`, `ALLOWED_UPLOAD_IMAGE_TYPES`, magic-byte validation  
- **Deployment:** `deploy/` — systemd, Nginx, Postgres backup/restore, `env.production.example`
- **Auth (login/register):** emails stored and matched **lowercased**; passwords **stripped** before bcrypt. **`401`** on login = invalid email/password (same message for both); **`409`** on register = duplicate email or username. Dev password reset: **`python scripts/set_user_password.py …`** from `backend/` (see `README.md` → Dev utilities).

_Update this file when routers, workers, or storage drivers change._
