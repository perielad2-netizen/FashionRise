import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limit import limiter as http_limiter
from app.core.logging_config import configure_logging
from app.db.session import SessionLocal, engine, get_db
from app.seed import run_seed_if_configured
from app.services.ai_worker import run_worker_tick

_log = logging.getLogger(__name__)

# After a missing-table error, skip further ticks until restart (avoids log spam before `alembic upgrade head`).
_ai_worker_skip_until_restart = False


def _database_label_safe() -> str:
    raw = get_settings().database_url
    if "://" in raw:
        raw = "postgresql://" + raw.split("://", 1)[1]
    try:
        p = urlparse(raw)
        db = (p.path or "/").lstrip("/") or "(no database)"
        host = p.hostname or "?"
        if p.port:
            return f"{host}:{p.port}/{db}"
        return f"{host}/{db}"
    except Exception:
        return "(unparseable DATABASE_URL)"


def _warn_if_missing_core_tables() -> None:
    if get_settings().testing:
        return
    try:
        insp = sa_inspect(engine)
        if insp.has_table("material_definitions"):
            return
    except Exception as e:
        _log.warning("Database inspection failed (is Postgres running?): %s", e)
        return
    _log.error(
        "Schema mismatch on %s: no `material_definitions` table. "
        "If `alembic upgrade head` did not print 'Running upgrade …', `alembic_version` may be ahead of actual tables. "
        "Dev fix (drops all data): from this repo's `backend/` folder run `alembic downgrade base` then `alembic upgrade head`. "
        "Confirm `DATABASE_URL` in backend/.env is the database you intend to use.",
        _database_label_safe(),
    )


def _worker_tick_blocking(batch_size: int) -> int:
    db = SessionLocal()
    try:
        return run_worker_tick(db, limit=batch_size)
    finally:
        db.close()


async def _ai_worker_loop(stop: asyncio.Event, poll_interval: float, batch_size: int) -> None:
    global _ai_worker_skip_until_restart
    while not stop.is_set():
        await asyncio.sleep(poll_interval)
        if stop.is_set():
            break
        if _ai_worker_skip_until_restart:
            continue
        try:
            # In a worker thread: an OpenAI image job can run for minutes, and blocking the
            # event loop would stall job polling, autosave and every other request with it.
            n = await asyncio.to_thread(_worker_tick_blocking, batch_size)
            if n:
                _log.debug("AI worker completed %s job(s)", n)
        except (ProgrammingError, OperationalError) as e:
            _ai_worker_skip_until_restart = True
            _log.warning(
                "AI worker stopped: database schema missing or unreachable (%s). "
                "From backend/: run `alembic upgrade head` (or `alembic downgrade base` then `alembic upgrade head` if stamped without tables), then restart.",
                e.__class__.__name__,
            )
        except Exception:
            _log.exception("AI worker tick failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_seed_if_configured()
    _warn_if_missing_core_tables()
    settings = get_settings()
    stop = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None
    if settings.ai_worker_enabled:
        interval = max(0.5, float(settings.ai_worker_poll_interval_seconds))
        worker_task = asyncio.create_task(
            _ai_worker_loop(stop, interval, max(1, int(settings.ai_worker_batch_size))),
            name="fashionrise_ai_worker",
        )
    yield
    stop.set()
    if worker_task is not None:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)

    app.state.limiter = http_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = settings.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/api/v1", tags=["ops"])
    def api_v1_root() -> dict[str, str]:
        """No resource lives at the bare prefix; this exists so `/api/v1` is not a silent 404 in browsers."""
        return {
            "api": "v1",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "hint": "Use concrete paths, e.g. /api/v1/materials or /api/v1/auth/login",
        }

    upload_root = Path(settings.local_storage_root) / settings.upload_subdir
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/uploads",
        StaticFiles(directory=str(upload_root)),
        name="static_uploads",
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe: process up (no database check). Use /ready for DB connectivity."""
        return {"status": "ok"}

    @app.get("/ready")
    def ready(db: Session = Depends(get_db)) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}

    return app


app = create_app()
