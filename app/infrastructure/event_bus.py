"""Redis Pub/Sub event bus — publishes SSE events to per-run channels."""

import json
import uuid

from redis.asyncio import Redis


class RedisEventBus:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def publish(self, run_id: uuid.UUID, event: dict) -> None:
        channel = f"run:{run_id}:events"
        await self._client.publish(channel, json.dumps(event))
