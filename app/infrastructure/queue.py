"""Redis List queue adapter — LPUSH to enqueue, BRPOP to dequeue."""

import uuid

from redis.asyncio import Redis

QUEUE_KEY = "runs:pending"


class RedisRunQueue:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def enqueue(self, run_id: uuid.UUID) -> None:
        await self._client.lpush(QUEUE_KEY, str(run_id))

    async def dequeue(self, timeout: int = 5) -> uuid.UUID | None:
        result = await self._client.brpop(QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, value = result
        return uuid.UUID(value)
