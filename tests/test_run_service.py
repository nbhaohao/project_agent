"""RunService use cases against in-memory fakes (no DB, no Redis)."""

import uuid

from app.application.run_service import RunService, cancel_run
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

    async def update(self, run: Run) -> None:
        self._store[run.id] = run


class FakeRunQueue:
    def __init__(self, log: list[str]) -> None:
        self.enqueued: list[uuid.UUID] = []
        self._log = log

    async def enqueue(self, run_id: uuid.UUID) -> None:
        self._log.append("enqueue")
        self.enqueued.append(run_id)

    async def dequeue(self, timeout: int = 5) -> uuid.UUID | None:
        return self.enqueued.pop(0) if self.enqueued else None


class FakeSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")


def _make_service() -> tuple[RunService, FakeRunRepository, FakeRunQueue, list[str]]:
    log: list[str] = []
    repo = FakeRunRepository()
    queue = FakeRunQueue(log)
    session = FakeSession(log)
    return RunService(session, repo, queue), repo, queue, log


async def test_submit_persists_queued_run():
    service, repo, queue, _ = _make_service()

    run = await service.submit("do a thing")

    assert run.status is RunStatus.QUEUED
    assert await service.get(run.id) == run


async def test_submit_enqueues_run_id():
    service, repo, queue, _ = _make_service()

    run = await service.submit("do a thing")

    assert run.id in queue.enqueued


async def test_submit_commits_before_enqueue():
    # Guards the worker race: the run must be committed to the DB before its id
    # lands in the queue, otherwise the worker SELECTs a row that isn't there yet.
    service, _, _, log = _make_service()

    await service.submit("do a thing")

    assert log == ["commit", "enqueue"]


async def test_get_unknown_returns_none():
    service, _, _, _ = _make_service()

    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_submitted_runs():
    service, _, _, _ = _make_service()
    await service.submit("a")
    await service.submit("b")

    runs = await service.list(limit=50, offset=0)

    assert len(runs) == 2


# --- cancel_run use case ---

class FakeCancelSignal:
    def __init__(self) -> None:
        self.requested: list[uuid.UUID] = []

    async def request(self, run_id: uuid.UUID) -> None:
        self.requested.append(run_id)

    async def is_requested(self, run_id: uuid.UUID) -> bool:
        return run_id in self.requested


async def test_cancel_queued_run_marks_cancelled():
    log: list[str] = []
    repo = FakeRunRepository()
    session = FakeSession(log)
    signal = FakeCancelSignal()

    run = Run.submit("do a thing")
    await repo.add(run)

    result = await cancel_run(run.id, runs=repo, signal=signal, session=session)

    assert result is not None
    assert result.status is RunStatus.CANCELLED
    assert run.id in signal.requested
    assert "commit" in log


async def test_cancel_unknown_run_returns_none():
    repo = FakeRunRepository()
    session = FakeSession([])
    signal = FakeCancelSignal()

    result = await cancel_run(uuid.uuid4(), runs=repo, signal=signal, session=session)

    assert result is None
    assert signal.requested == []


async def test_cancel_terminal_run_is_idempotent():
    repo = FakeRunRepository()
    session = FakeSession([])
    signal = FakeCancelSignal()

    run = Run.submit("do a thing")
    run.mark_running()
    run.mark_succeeded("done")
    await repo.add(run)

    result = await cancel_run(run.id, runs=repo, signal=signal, session=session)

    assert result is not None
    assert result.status is RunStatus.SUCCEEDED  # unchanged
    assert signal.requested == []  # no signal set
