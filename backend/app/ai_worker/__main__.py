"""Standalone AI job consumer for split deployments (see ``python -m app.ai_worker --help``)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.session import SessionLocal
from app.services.ai_worker import run_worker_tick


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="FashionRise AI worker: polls the database for queued ai_jobs rows and completes them "
        "(stub provider until real inference is wired).",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Run a single batch tick then exit (handy for cron or smoke checks).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    log = logging.getLogger("app.ai_worker")

    interval = max(0.5, float(settings.ai_worker_poll_interval_seconds))
    batch = max(1, int(settings.ai_worker_batch_size))

    log.info(
        "FashionRise AI worker starting (poll=%.2fs batch=%s once=%s)",
        interval,
        batch,
        args.once,
    )

    stop = False

    def _handle_stop(_signum: int, _frame: object | None) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop)

    def tick() -> int:
        db = SessionLocal()
        try:
            return run_worker_tick(db, limit=batch)
        finally:
            db.close()

    if args.once:
        try:
            n = tick()
        except Exception:
            log.exception("AI worker tick failed")
            return 1
        if n:
            log.info("Processed %s AI job(s)", n)
        return 0

    while not stop:
        time.sleep(interval)
        if stop:
            break
        try:
            n = tick()
            if n:
                log.info("Processed %s AI job(s)", n)
        except Exception:
            log.exception("AI worker tick failed")

    log.info("FashionRise AI worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
