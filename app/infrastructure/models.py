"""SQLAlchemy ORM models — the persistence shape of domain entities."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.run import RunStatus
from app.infrastructure.db import Base


class RunORM(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    input: Mapped[str] = mapped_column(String)
    status: Mapped[RunStatus] = mapped_column(
        # store the lowercase .value ("queued"), not the member name
        Enum(RunStatus, name="run_status", values_callable=lambda e: [m.value for m in e])
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
