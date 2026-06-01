"""SQLAlchemy adapter for the RunRepository port — maps ORM <-> domain."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.run import Run
from app.infrastructure.models import RunORM


def _to_orm(run: Run) -> RunORM:
    return RunORM(
        id=run.id, input=run.input, status=run.status, created_at=run.created_at
    )


def _to_domain(orm: RunORM) -> Run:
    return Run(
        id=orm.id, input=orm.input, status=orm.status, created_at=orm.created_at
    )


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
