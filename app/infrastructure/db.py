"""Async SQLAlchemy engine + session factory + ORM base (Postgres via asyncpg)."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)


@event.listens_for(engine.sync_engine, "connect")
def _register_vector_codec(dbapi_connection, _connection_record):
    # asyncpg needs explicit codec registration to serialise/deserialise vector columns.
    from pgvector.asyncpg import register_vector
    dbapi_connection.run_sync(register_vector)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models; carries the metadata Alembic targets."""
