"""Run domain model — one agent execution.

M1 scope: a Run can only be *submitted* (born QUEUED) and read back.
State transitions (mark_running / mark_succeeded / ...) are intentionally NOT
here yet — no code drives them until the M2 worker exists (YAGNI).
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.ids import new_uuid7


class RunStatus(str, enum.Enum):
    # Full lifecycle vocabulary defined up front (it is the status column's
    # value domain — defining it now avoids later ALTER TYPE migrations).
    # Only QUEUED is produced in M1; the rest are driven from M2 onward.
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Run:
    id: uuid.UUID
    input: str
    status: RunStatus
    created_at: datetime

    @classmethod
    def submit(cls, input: str) -> Run:
        return cls(
            id=new_uuid7(),
            input=input,
            status=RunStatus.QUEUED,
            created_at=datetime.now(UTC),
        )
