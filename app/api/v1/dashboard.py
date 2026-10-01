"""Dashboard route."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_service, require
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.dashboard import DashboardRead
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardRead)
async def get_dashboard(
    actor: Annotated[User, Depends(require(Permission.DASHBOARD_READ))],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardRead:
    return await service.get_dashboard(actor)
