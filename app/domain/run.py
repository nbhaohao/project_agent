"""Run domain model — one agent execution.

M3: added result/error fields; mark_succeeded/mark_failed now store the outcome.
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


class InvalidTransition(Exception):
    pass


class RunCancelled(Exception):
    """Raised by AgentLoop when a cancel signal is detected mid-execution."""


@dataclass
class Run:
    id: uuid.UUID
    input: str
    status: RunStatus
    created_at: datetime
    result: str | None = None
    error: str | None = None

    @classmethod
    def submit(cls, input: str) -> Run:
        return cls(
            id=new_uuid7(),
            input=input,
            status=RunStatus.QUEUED,
            created_at=datetime.now(UTC),
        )

    def mark_running(self) -> None:
        if self.status is not RunStatus.QUEUED:
            raise InvalidTransition(f"cannot mark running from {self.status}")
        self.status = RunStatus.RUNNING

    def mark_succeeded(self, result: str | None = None) -> None:
        if self.status is not RunStatus.RUNNING:
            raise InvalidTransition(f"cannot mark succeeded from {self.status}")
        self.status = RunStatus.SUCCEEDED
        self.result = result

    def mark_failed(self, error: str | None = None) -> None:
        if self.status is not RunStatus.RUNNING:
            raise InvalidTransition(f"cannot mark failed from {self.status}")
        self.status = RunStatus.FAILED
        self.error = error

    def mark_cancelled(self) -> None:
        if self.status not in (RunStatus.QUEUED, RunStatus.RUNNING):
            raise InvalidTransition(f"cannot mark cancelled from {self.status}")
        self.status = RunStatus.CANCELLED
