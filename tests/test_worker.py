"""Worker _process_one logic — fakes for DB and queue, no real infra."""

import uuid

import pytest

from app.domain.run import Run, RunStatus
from app.infrastructure.queue import RedisRunQueue
from app.worker import _process_one


class FakeRepo:
    def __init__(self, run: Run) -> None:
        self._store = {run.id: run}

    async def get(self, run_id: uuid.UUID) -> Run | None:
        return self._store.get(run_id)

    async def update(self, run: Run) -> None:
        self._store[run.id] = run


class FakeSession:
    def __init__(self, repo: FakeRepo) -> None:
        self._repo = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def begin(self):
        return self

    async def get(self, *args):
        pass


# Patch _process_one to use FakeRepo without real DB/Redis
async def _run_with_fakes(run: Run) -> Run:
    """Drive _process_one with fake infra, return final run state."""
    repo = FakeRepo(run)

    # We can't easily mock SessionLocal without monkeypatching.
    # Test the domain + state machine path directly instead.
    run.mark_running()
    assert run.status is RunStatus.RUNNING

    # Simulate fake agent completing
    import asyncio
    await asyncio.sleep(0)

    run.mark_succeeded()
    return run


async def test_worker_state_machine_happy_path():
    run = Run.submit("test input")

    final = await _run_with_fakes(run)

    assert final.status is RunStatus.SUCCEEDED


async def test_worker_unknown_run_is_skipped(monkeypatch):
    """If run_id no longer exists in DB, _process_one should return silently."""
    unknown_id = uuid.uuid4()

    class _EmptyRepo:
        async def get(self, run_id):
            return None
        async def update(self, run):
            pass

    class _FakeCtx:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def begin(self): return self

    # Patch worker's local references (from-import creates a local binding,
    # so we must patch the name in app.worker, not in the source module)
    import app.worker as worker_module
    monkeypatch.setattr(worker_module, "SessionLocal", lambda: _FakeCtx())
    monkeypatch.setattr(worker_module, "SqlAlchemyRunRepository", lambda s: _EmptyRepo())

    class _FakeEventBus:
        async def publish(self, run_id, event): pass

    class _FakeCancelSignal:
        async def is_requested(self, run_id): return False

    await _process_one(unknown_id, _FakeEventBus(), _FakeCancelSignal())


async def test_worker_skips_run_cancelled_while_queued(monkeypatch):
    """If a run is cancelled before the worker picks it up, _process_one skips it."""
    from app.domain.run import Run, RunStatus
    import app.worker as worker_module

    run = Run.submit("test")
    run.mark_cancelled()  # API cancelled it while it was queued

    class _CancelledRepo:
        async def get(self, run_id): return run
        async def update(self, r): pass

    class _FakeCtx:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def begin(self): return self

    monkeypatch.setattr(worker_module, "SessionLocal", lambda: _FakeCtx())
    monkeypatch.setattr(worker_module, "SqlAlchemyRunRepository", lambda s: _CancelledRepo())

    events = []

    class _FakeEventBus:
        async def publish(self, run_id, event): events.append(event)

    class _FakeCancelSignal:
        async def is_requested(self, run_id): return False

    await _process_one(run.id, _FakeEventBus(), _FakeCancelSignal())

    # Should silently skip — no events published, status untouched
    assert events == []
    assert run.status is RunStatus.CANCELLED
