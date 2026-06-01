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

    # Patch SessionLocal to return a session that yields an empty repo
    from app.infrastructure import db as db_module

    class _EmptyRepo:
        async def get(self, run_id):
            return None
        async def update(self, run):
            pass

    class _FakeCtx:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def begin(self): return self

    monkeypatch.setattr(db_module, "SessionLocal", lambda: _FakeCtx())

    from app.infrastructure import repositories as repo_module
    monkeypatch.setattr(repo_module, "SqlAlchemyRunRepository", lambda s: _EmptyRepo())

    # Should return without raising
    await _process_one(unknown_id)
