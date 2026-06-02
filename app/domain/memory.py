"""Memory domain model — one piece of cross-run long-term knowledge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.ids import new_uuid7


@dataclass
class Memory:
    id: uuid.UUID
    content: str
    created_at: datetime

    @classmethod
    def create(cls, content: str) -> Memory:
        return cls(id=new_uuid7(), content=content, created_at=datetime.now(UTC))
