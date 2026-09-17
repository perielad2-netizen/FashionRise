"""The in-process AI worker must stay off the event loop.

A Create Real Design job runs an OpenAI JSON call plus up to three blueprint images. Running
that on the loop froze every other request (job polling, autosave) for minutes at a time.
"""

import asyncio
import contextlib
import threading
import time

from app import main as app_main


def test_worker_tick_runs_off_the_event_loop(monkeypatch):
    tick_threads: list[str] = []

    def fake_tick(batch_size: int) -> int:
        assert batch_size == 3
        tick_threads.append(threading.current_thread().name)
        time.sleep(0.25)
        return 1

    monkeypatch.setattr(app_main, "_worker_tick_blocking", fake_tick)
    monkeypatch.setattr(app_main, "_ai_worker_skip_until_restart", False)

    async def scenario() -> tuple[int, float]:
        stop = asyncio.Event()
        task = asyncio.create_task(app_main._ai_worker_loop(stop, 0.01, 3))
        slices = 0
        started = time.monotonic()
        while slices < 20:
            await asyncio.sleep(0.02)
            slices += 1
        elapsed = time.monotonic() - started
        stop.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return slices, elapsed

    slices, elapsed = asyncio.run(scenario())

    assert slices == 20
    assert tick_threads, "worker never ran a tick"
    assert all(name != "MainThread" for name in tick_threads), tick_threads
    # 20 x 20ms of unrelated work keeps its own pace while ticks are in flight.
    assert elapsed < 1.5, f"event loop was stalled by the worker ({elapsed:.2f}s)"


def test_worker_tick_opens_and_closes_its_own_session(monkeypatch):
    closed: list[bool] = []

    class FakeSession:
        def close(self) -> None:
            closed.append(True)

    session = FakeSession()
    monkeypatch.setattr(app_main, "SessionLocal", lambda: session)
    monkeypatch.setattr(app_main, "run_worker_tick", lambda db, limit: 2 if db is session else 0)

    assert app_main._worker_tick_blocking(5) == 2
    assert closed == [True]
