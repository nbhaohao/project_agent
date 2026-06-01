"""Use cases for Runs — orchestrates domain + repository port."""

import uuid

from app.application.ports import RunQueue, RunRepository
from app.domain.run import Run


class RunService:
    def __init__(self, runs: RunRepository, queue: RunQueue) -> None:
        self._runs = runs
        self._queue = queue

    async def submit(self, input: str) -> Run:
        run = Run.submit(input)
        await self._runs.add(run)
        await self._queue.enqueue(run.id)
        return run

    async def get(self, run_id: uuid.UUID) -> Run | None:
        return await self._runs.get(run_id)

    async def list(self, limit: int = 50, offset: int = 0) -> list[Run]:
        return await self._runs.list(limit=limit, offset=offset)
