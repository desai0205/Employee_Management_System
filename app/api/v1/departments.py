"""Department routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    Caller,
    get_caller,
    get_department_service,
    get_page_params,
    require,
)
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.common import Page
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.department import DepartmentService

router = APIRouter()


@router.get("", response_model=Page[DepartmentRead])
async def list_departments(
    _actor: Annotated[User, Depends(require(Permission.DEPARTMENTS_READ))],
    service: Annotated[DepartmentService, Depends(get_department_service)],
    params: Annotated[PageParams, Depends(get_page_params)],
) -> Page[DepartmentRead]:
    return await service.list_departments(params)


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.DEPARTMENTS_WRITE))],
    service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
    return await service.create_department(actor, payload, ip_address=caller.ip_address)


@router.get("/{department_id}", response_model=DepartmentRead)
async def get_department(
    department_id: uuid.UUID,
    _actor: Annotated[User, Depends(require(Permission.DEPARTMENTS_READ))],
    service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
    return await service.get_department(department_id)


@router.patch("/{department_id}", response_model=DepartmentRead)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.DEPARTMENTS_WRITE))],
    service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
    return await service.update_department(
        actor, department_id, payload, ip_address=caller.ip_address
    )
