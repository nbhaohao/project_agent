"""Redis-backed cancel signal — SET a key to request, EXISTS to poll."""

import uuid

from redis.asyncio import Redis

_TTL_SECONDS = 3600  # auto-expire stale signals after an hour


class RedisCancelSignal:
    def __init__(self, client: Redis) -> None:
        self._client = client

    def _key(self, run_id: uuid.UUID) -> str:
        return f"run:{run_id}:cancel"

    async def request(self, run_id: uuid.UUID) -> None:
        await self._client.set(self._key(run_id), "1", ex=_TTL_SECONDS)

    async def is_requested(self, run_id: uuid.UUID) -> bool:
        return bool(await self._client.exists(self._key(run_id)))
