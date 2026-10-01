"""Append-only audit events recorded in the same transaction as the change."""

import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.core.logging import current_request_id
from app.core.pagination import PageParams
from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit import AuditLogRead
from app.schemas.common import Page


def _json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def snapshot(source: object, fields: list[str]) -> dict[str, Any]:
    return {field: _json_value(getattr(source, field)) for field in fields}


class AuditService:
    def __init__(
        self,
        repository: AuditLogRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self._clock = clock or utc_now

    async def record(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            before=before,
            after=after,
            ip_address=ip_address,
            request_id=current_request_id(),
            created_at=self._clock(),
        )
        await self.repository.add_entry(entry)

    async def list_logs(
        self,
        params: PageParams,
        *,
        actor_user_id: uuid.UUID | None,
        entity_type: str | None,
        entity_id: str | None,
        action: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> Page[AuditLogRead]:
        rows, total, pages = await self.repository.list_page(
            params,
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            created_from=created_from,
            created_to=created_to,
        )
        return Page(
            items=[AuditLogRead.model_validate(row) for row in rows],
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=pages,
        )
