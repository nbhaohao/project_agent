"""Shared async Redis clients."""

from redis.asyncio import Redis

from app.config import settings

# General-purpose client — used for LPUSH/BRPOP/PUBLISH
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)

# Dedicated client for Pub/Sub SUBSCRIBE+LISTEN — socket_timeout=None prevents
# read timeouts on long-lived blocking connections (unlike BRPOP which has a
# built-in timeout we catch; pubsub.listen() must block indefinitely)
pubsub_redis: Redis = Redis.from_url(
    settings.redis_url, decode_responses=True, socket_timeout=None
)
