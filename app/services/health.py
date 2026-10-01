"""Readiness checks for PostgreSQL and Redis."""

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError


class HealthService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.redis = redis

    async def ready(self) -> dict[str, str]:
        try:
            await self.session.execute(text("SELECT 1"))
        except Exception as exc:
            raise AppError(
                "database_unavailable", "Database is unavailable.", status_code=503
            ) from exc
        try:
            await self.redis.ping()
        except Exception as exc:
            raise AppError(
                "redis_unavailable", "Redis is unavailable.", status_code=503
            ) from exc
        return {"status": "ok", "database": "ok", "redis": "ok"}
