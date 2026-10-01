"""Jobs scheduled during a request are enqueued only after the transaction commits."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar

Job = tuple[str, tuple[object, ...]]
Dispatcher = Callable[[list[Job]], Awaitable[None]]

_pending: ContextVar[list[Job] | None] = ContextVar("pending_jobs", default=None)
_rollback_only: ContextVar[bool] = ContextVar("rollback_only", default=False)
_dispatcher: Dispatcher | None = None


def set_job_dispatcher(dispatcher: Dispatcher) -> None:
    global _dispatcher
    _dispatcher = dispatcher


def reset_job_state() -> None:
    _pending.set([])
    _rollback_only.set(False)


def schedule_job(name: str, *args: object) -> None:
    jobs = _pending.get()
    if jobs is None:
        jobs = []
        _pending.set(jobs)
    jobs.append((name, args))


def pending_jobs() -> list[Job]:
    return list(_pending.get() or [])


def mark_rollback() -> None:
    _rollback_only.set(True)


def should_rollback() -> bool:
    return _rollback_only.get()


def discard_jobs() -> None:
    _pending.set([])


async def dispatch_jobs() -> None:
    jobs = _pending.get() or []
    _pending.set([])
    if not jobs or _dispatcher is None:
        return
    await _dispatcher(jobs)
