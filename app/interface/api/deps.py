"""FastAPI dependency wiring for the interface layer."""

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.run_service import RunService
from app.infrastructure.db import SessionLocal
from app.infrastructure.repositories import SqlAlchemyRunRepository


async def get_session() -> AsyncIterator[AsyncSession]:
    # One transaction per request: commit on success, rollback on exception.
    async with SessionLocal() as session, session.begin():
        yield session


def get_run_service(
    session: AsyncSession = Depends(get_session),
) -> RunService:
    return RunService(SqlAlchemyRunRepository(session))
