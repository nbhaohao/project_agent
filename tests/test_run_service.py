"""RunService use cases against an in-memory fake repository (no DB)."""

import uuid

from app.application.run_service import RunService
from app.domain.run import Run, RunStatus


class FakeRunRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Run] = {}

    async def add(self, run: Run) -> None:
        self._store[run.id] = run

    async def get(self, run_id: uuid.UUID) -> Run | None:
        return self._store.get(run_id)

    async def list(self, limit: int, offset: int) -> list[Run]:
        runs = sorted(self._store.values(), key=lambda r: r.created_at, reverse=True)
        return runs[offset : offset + limit]


async def test_submit_persists_queued_run():
    service = RunService(FakeRunRepository())

    run = await service.submit("do a thing")

    assert run.status is RunStatus.QUEUED
    assert await service.get(run.id) == run


async def test_get_unknown_returns_none():
    service = RunService(FakeRunRepository())

    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_submitted_runs():
    service = RunService(FakeRunRepository())
    await service.submit("a")
    await service.submit("b")

    runs = await service.list(limit=50, offset=0)

    assert len(runs) == 2
