"""Redis-backed login attempt limiter."""

from typing import Protocol

from redis.asyncio import Redis

from app.core.exceptions import AppError


class RateLimiter(Protocol):
    async def hit(self, email: str, ip: str | None) -> None: ...


class LoginRateLimiter:
    def __init__(self, client: Redis, limit: int, window_seconds: int) -> None:
        self._client = client
        self._limit = limit
        self._window = window_seconds

    async def hit(self, email: str, ip: str | None) -> None:
        keys = [f"login:email:{email.lower()}"]
        if ip:
            keys.append(f"login:ip:{ip}")
        for key in keys:
            count = int(await self._client.incr(key))
            if count == 1:
                await self._client.expire(key, self._window)
            if count > self._limit:
                raise AppError(
                    "rate_limited",
                    "Too many login attempts. Try again later.",
                    status_code=429,
                )
