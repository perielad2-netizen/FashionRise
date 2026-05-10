from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import configure_logging
from app.db.session import get_db
from app.seed import run_seed_if_configured


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_seed_if_configured()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)

    origins = settings.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

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
