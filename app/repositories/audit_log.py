"""Audit log append and admin reads."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.models.audit_log import AuditLog
from app.repositories.base import Repository, paginate, sort_column


class AuditLogRepository(Repository[AuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def exists_notification(self, entity_id: str, status: str) -> bool:
        statement = select(AuditLog.id).where(
            AuditLog.action == "notification.leave_decision",
            AuditLog.entity_id == entity_id,
            AuditLog.after["status"].astext == status,
        )
        result = await self.session.scalars(statement)
        return result.first() is not None

    async def list_page(
        self,
        params: PageParams,
        *,
        actor_user_id: uuid.UUID | None,
        entity_type: str | None,
        entity_id: str | None,
        action: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[list[AuditLog], int, int]:
        statement = select(AuditLog)
        if actor_user_id is not None:
            statement = statement.where(AuditLog.actor_user_id == actor_user_id)
        if entity_type is not None:
            statement = statement.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            statement = statement.where(AuditLog.entity_id == entity_id)
        if action is not None:
            statement = statement.where(AuditLog.action == action)
        if created_from is not None:
            statement = statement.where(AuditLog.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(AuditLog.created_at <= created_to)
        ordering = sort_column(
            params.sort,
            params.order,
            {"created_at": AuditLog.created_at, "action": AuditLog.action},
            default="created_at",
        )
        if params.sort is None:
            ordering = AuditLog.created_at.desc()
        rows, total, pages = await paginate(self.session, statement, params, ordering)
        return rows, total, pages

    async def add_entry(self, entry: AuditLog) -> None:
        self.session.add(entry)
        await self.session.flush()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return value
