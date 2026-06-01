"""Use cases for Runs — orchestrates domain + repository port."""

import uuid

from app.application.ports import RunRepository
from app.domain.run import Run


class RunService:
    def __init__(self, runs: RunRepository) -> None:
        self._runs = runs

    async def submit(self, input: str) -> Run:
        run = Run.submit(input)
        await self._runs.add(run)
        return run

    async def get(self, run_id: uuid.UUID) -> Run | None:
        return await self._runs.get(run_id)

    async def list(self, limit: int = 50, offset: int = 0) -> list[Run]:
        return await self._runs.list(limit=limit, offset=offset)
