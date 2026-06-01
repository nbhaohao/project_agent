"""Ports (interfaces) the application layer depends on.

Infrastructure provides the adapters; the application never imports infra directly.
"""

import uuid
from typing import Any, Protocol

from app.domain.run import Run


class RunRepository(Protocol):
    async def add(self, run: Run) -> None: ...

    async def get(self, run_id: uuid.UUID) -> Run | None: ...

    async def list(self, limit: int, offset: int) -> list[Run]: ...

    async def update(self, run: Run) -> None: ...


class RunQueue(Protocol):
    async def enqueue(self, run_id: uuid.UUID) -> None: ...

    async def dequeue(self, timeout: int = 5) -> uuid.UUID | None: ...


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
    ) -> Any:
        # Returns an object with .content (list of blocks) and .stop_reason (str).
        # Structurally matches anthropic.types.Message — duck-typed to stay
        # provider-agnostic without a full mapping layer (YAGNI until provider 2).
        ...
