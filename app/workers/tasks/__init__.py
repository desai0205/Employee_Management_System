"""Background jobs. Each job re-reads the database and calls a service."""

import asyncio
import uuid
from typing import Any

from arq import Retry
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.session import get_session_factory, run_transaction
from app.services.container import build_leave_service, build_report_service
from app.services.maintenance import build_maintenance_service

logger = get_logger(__name__)


async def wait_for_schema() -> None:
    factory = get_session_factory()
    for _attempt in range(30):
        try:
            async with factory() as session:
                await session.execute(text("SELECT 1 FROM users LIMIT 1"))
            return
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError("Database schema is not ready.")


async def notify_leave_decision(ctx: dict[str, Any], leave_request_id: str) -> None:
    request_id = uuid.UUID(leave_request_id)

    async def work(session: Any) -> None:
        await build_leave_service(session).record_notification(request_id)

    try:
        await run_transaction(work)
    except NotFoundError as exc:
        if int(ctx.get("job_try", 1)) >= 5:
            logger.error(
                "leave_notification_missing", leave_request_id=leave_request_id
            )
            return
        raise Retry(defer=2) from exc


async def generate_report_export(ctx: dict[str, Any], export_id: str) -> None:
    parsed = uuid.UUID(export_id)
    final_attempt = int(ctx.get("job_try", 1)) >= 5

    async def work(session: Any) -> None:
        await build_report_service(session).generate_export(
            parsed, final_attempt=final_attempt
        )

    try:
        await run_transaction(work)
    except NotFoundError as exc:
        if final_attempt:
            logger.error("report_export_missing", export_id=export_id)
            return
        raise Retry(defer=2) from exc


async def purge_expired_refresh_tokens(_ctx: dict[str, Any]) -> None:
    async def work(session: Any) -> None:
        removed = await build_maintenance_service(session).purge_expired_tokens()
        logger.info("refresh_tokens_purged", removed=removed)

    await run_transaction(work)


async def mark_missing_attendance(_ctx: dict[str, Any]) -> None:
    async def work(session: Any) -> None:
        created = await build_maintenance_service(session).mark_missing_attendance()
        logger.info("missing_attendance_marked", created=created)

    await run_transaction(work)


async def sweep_report_exports(_ctx: dict[str, Any]) -> None:
    async def work(session: Any) -> list[uuid.UUID]:
        return await build_report_service(session).pending_export_ids()

    pending = await run_transaction(work)
    for export_id in pending:
        await generate_report_export({"job_try": 1}, str(export_id))
