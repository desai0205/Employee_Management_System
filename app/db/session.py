"""Async engine, session factory, and explicit transaction helper for workers."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.post_commit import (
    discard_jobs,
    dispatch_jobs,
    reset_job_state,
    should_rollback,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "db_session", default=None
)


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    if _session_factory is None:
        raise RuntimeError("Session factory is not initialized.")
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def set_current_session(session: AsyncSession) -> Token[AsyncSession | None]:
    return _current_session.set(session)


def reset_current_session(token: Token[AsyncSession | None]) -> None:
    _current_session.reset(token)


def current_session() -> AsyncSession:
    session = _current_session.get()
    if session is None:
        raise RuntimeError("No database session is bound to this request.")
    return session


async def run_transaction[T](work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Commit a worker unit of work, then enqueue jobs scheduled inside it."""
    factory = get_session_factory()
    async with factory() as session:
        token = set_current_session(session)
        reset_job_state()
        try:
            result = await work(session)
            await session.commit()
            await dispatch_jobs()
            return result
        except Exception:
            await session.rollback()
            discard_jobs()
            raise
        finally:
            reset_current_session(token)


async def finish_request_transaction(session: AsyncSession) -> None:
    if should_rollback():
        await session.rollback()
        discard_jobs()
        return
    await session.commit()
    await dispatch_jobs()
