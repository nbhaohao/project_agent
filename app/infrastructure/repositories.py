"""SQLAlchemy adapter for the RunRepository port — maps ORM <-> domain."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.message import RunMessage
from app.domain.run import Run
from app.infrastructure.models import RunMessageORM, RunORM


def _to_orm(run: Run) -> RunORM:
    return RunORM(
        id=run.id, input=run.input, status=run.status, created_at=run.created_at
    )


def _to_domain(orm: RunORM) -> Run:
    return Run(
        id=orm.id,
        input=orm.input,
        status=orm.status,
        created_at=orm.created_at,
        result=orm.result,
        error=orm.error,
    )


class SqlAlchemyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: RunMessage) -> None:
        self._session.add(RunMessageORM(
            id=message.id,
            run_id=message.run_id,
            seq=message.seq,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        ))

    async def list_for_run(self, run_id: uuid.UUID) -> list[RunMessage]:
        result = await self._session.execute(
            select(RunMessageORM)
            .where(RunMessageORM.run_id == run_id)
            .order_by(RunMessageORM.seq)
        )
        return [
            RunMessage(
                id=orm.id,
                run_id=orm.run_id,
                seq=orm.seq,
                role=orm.role,
                content=orm.content,
                created_at=orm.created_at,
            )
            for orm in result.scalars().all()
        ]


class SqlAlchemyRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: Run) -> None:
        self._session.add(_to_orm(run))

    async def get(self, run_id: uuid.UUID) -> Run | None:
        orm = await self._session.get(RunORM, run_id)
        return _to_domain(orm) if orm is not None else None

    async def list(self, limit: int, offset: int) -> list[Run]:
        result = await self._session.execute(
            select(RunORM)
            .order_by(RunORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(orm) for orm in result.scalars().all()]

    async def update(self, run: Run) -> None:
        orm = await self._session.get(RunORM, run.id)
        if orm is None:
            raise ValueError(f"Run {run.id} not found")
        orm.status = run.status
        orm.result = run.result
        orm.error = run.error
