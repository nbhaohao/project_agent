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
