"""FastAPI dependency wiring for the interface layer."""

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.run_service import RunService
from app.infrastructure.cancel import RedisCancelSignal
from app.infrastructure.db import SessionLocal
from app.infrastructure.queue import RedisRunQueue
from app.infrastructure.redis import redis_client
from app.infrastructure.repositories import SqlAlchemyRunRepository


async def get_session() -> AsyncIterator[AsyncSession]:
    # Transaction boundary is owned by the use case (RunService), not the request:
    # submit() must commit the run BEFORE enqueueing it, so the request can't hold
    # an open transaction across the enqueue.
    async with SessionLocal() as session:
        yield session


def get_run_service(
    session: AsyncSession = Depends(get_session),
) -> RunService:
    return RunService(session, SqlAlchemyRunRepository(session), RedisRunQueue(redis_client))


def get_cancel_signal() -> RedisCancelSignal:
    return RedisCancelSignal(redis_client)
