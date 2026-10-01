"""Async Redis client lifecycle."""

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


async def init_redis() -> Redis:
    global _client
    client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.ping()
    _client = client
    return client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


def get_redis_client() -> Redis:
    if _client is None:
        raise RuntimeError("Redis is not initialized.")
    return _client
