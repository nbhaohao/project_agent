"""Ports (interfaces) the application layer depends on.

Infrastructure provides the adapters; the application never imports infra directly.
"""

import uuid
from typing import Protocol

from app.domain.run import Run


class RunRepository(Protocol):
    async def add(self, run: Run) -> None: ...

    async def get(self, run_id: uuid.UUID) -> Run | None: ...

    async def list(self, limit: int, offset: int) -> list[Run]: ...

    async def update(self, run: Run) -> None: ...


class RunQueue(Protocol):
    async def enqueue(self, run_id: uuid.UUID) -> None: ...

    async def dequeue(self, timeout: int = 5) -> uuid.UUID | None: ...
