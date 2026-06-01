"""RunMessage domain model — one persisted message in an agent run's conversation."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.ids import new_uuid7


@dataclass
class RunMessage:
    id: uuid.UUID
    run_id: uuid.UUID
    seq: int          # ordering within a run, 0-indexed
    role: str         # "user" | "assistant"
    content: list     # Anthropic-format content blocks as plain dicts
    created_at: datetime

    @classmethod
    def create(cls, run_id: uuid.UUID, seq: int, role: str, content: list) -> "RunMessage":
        return cls(
            id=new_uuid7(),
            run_id=run_id,
            seq=seq,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
