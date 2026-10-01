"""arq worker configuration."""

from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.db.session import dispose_engine
from app.workers.tasks import (
    generate_report_export,
    mark_missing_attendance,
    notify_leave_decision,
    purge_expired_refresh_tokens,
    sweep_report_exports,
    wait_for_schema,
)


async def startup(_ctx: dict[str, Any]) -> None:
    get_settings().validate_runtime()
    await wait_for_schema()


async def shutdown(_ctx: dict[str, Any]) -> None:
    await dispose_engine()


class WorkerSettings:
    functions = [
        notify_leave_decision,
        generate_report_export,
        purge_expired_refresh_tokens,
        mark_missing_attendance,
        sweep_report_exports,
    ]
    cron_jobs = [
        cron(purge_expired_refresh_tokens, hour=3, minute=0),  # type: ignore[arg-type]
        cron(mark_missing_attendance, hour=1, minute=15),  # type: ignore[arg-type]
        cron(sweep_report_exports, minute=set(range(0, 60, 5))),  # type: ignore[arg-type]
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = startup
    on_shutdown = shutdown
