"""Admin audit log reads."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, get_page_params, require
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.audit import AuditLogRead
from app.schemas.common import Page
from app.services.audit import AuditService

router = APIRouter()


@router.get("", response_model=Page[AuditLogRead])
async def list_audit_logs(
    _actor: Annotated[User, Depends(require(Permission.AUDIT_READ))],
    service: Annotated[AuditService, Depends(get_audit_service)],
    params: Annotated[PageParams, Depends(get_page_params)],
    actor_user_id: Annotated[uuid.UUID | None, Query()] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> Page[AuditLogRead]:
    return await service.list_logs(
        params,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        created_from=created_from,
        created_to=created_to,
    )
