"""Use cases for Runs — orchestrates domain + repository port."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import CancelSignal, RunQueue, RunRepository
from app.domain.run import Run, RunStatus

_TERMINAL = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}


async def cancel_run(
    run_id: uuid.UUID,
    *,
    runs: RunRepository,
    signal: CancelSignal,
    session: AsyncSession,
) -> Run | None:
    run = await runs.get(run_id)
    if run is None:
        return None
    if run.status in _TERMINAL:
        return run  # idempotent
    if run.status is RunStatus.QUEUED:
        # Not yet picked up by worker — mark directly; worker will skip on dequeue
        run.mark_cancelled()
        await runs.update(run)
        await session.commit()
    # For RUNNING: signal only — worker detects and marks_cancelled itself
    await signal.request(run_id)
    return run


class RunService:
    def __init__(self, session: AsyncSession, runs: RunRepository, queue: RunQueue) -> None:
        self._session = session
        self._runs = runs
        self._queue = queue

    async def submit(self, input: str) -> Run:
        run = Run.submit(input)
        await self._runs.add(run)
        # Persist BEFORE enqueue: the worker pulls the id from Redis and
        # immediately SELECTs the run. If we enqueue before commit, the worker
        # races ahead and sees no row → "run not found, skipping".
        await self._session.commit()
        await self._queue.enqueue(run.id)
        return run

    async def get(self, run_id: uuid.UUID) -> Run | None:
        return await self._runs.get(run_id)

    async def list(self, limit: int = 50, offset: int = 0) -> list[Run]:
        return await self._runs.list(limit=limit, offset=offset)
