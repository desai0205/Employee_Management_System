"""Integration fixtures. Docker provides PostgreSQL and Redis."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.post_commit import set_job_dispatcher
from app.db.redis import close_redis, init_redis
from app.db.session import dispose_engine, get_session_factory
from app.main import create_app
from app.workers.queue import close_queue, enqueue_jobs, init_queue


def _asyncpg_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))


def _docker_available() -> bool:
    return Path("/var/run/docker.sock").exists()


@pytest.fixture(scope="session")
def database_urls() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.skip("Docker is required for integration tests")
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    postgres = PostgresContainer("postgres:16-alpine")
    redis = RedisContainer("redis:7-alpine")
    postgres.start()
    redis.start()
    database_url = _asyncpg_url(postgres.get_connection_url())
    redis_url = (
        f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
    )
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    yield database_url, redis_url
    postgres.stop()
    redis.stop()


@pytest.fixture
async def client(database_urls: tuple[str, str]) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = database_urls[0]
    os.environ["REDIS_URL"] = database_urls[1]
    get_settings.cache_clear()
    await dispose_engine()
    await init_redis()
    await init_queue()
    set_job_dispatcher(enqueue_jobs)
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            text(
                "TRUNCATE report_exports, audit_logs, leave_requests, leave_balances, "
                "leave_types, attendance_records, refresh_tokens, employees, "
                "departments, users RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        yield api
    await close_queue()
    await close_redis()
    await dispose_engine()
