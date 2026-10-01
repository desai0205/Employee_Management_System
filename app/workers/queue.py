"""arq Redis pool used to enqueue jobs after a successful commit."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.post_commit import Job

logger = get_logger(__name__)
_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def init_queue() -> None:
    global _pool
    _pool = await create_pool(redis_settings())


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
    _pool = None


async def enqueue_jobs(jobs: list[Job]) -> None:
    if _pool is None:
        logger.error("queue_not_initialized", jobs=len(jobs))
        return
    try:
        for name, args in jobs:
            await _pool.enqueue_job(name, *args)
    except Exception:
        logger.exception("enqueue_failed", jobs=len(jobs))
