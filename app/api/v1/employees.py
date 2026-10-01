"""Employee routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    Caller,
    get_caller,
    get_employee_service,
    get_page_params,
    require,
)
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.models.enums import EmploymentStatus
from app.models.user import User
from app.schemas.common import Page
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeRead,
    EmployeeTerminate,
    EmployeeUpdate,
)
from app.services.employee import EmployeeService

router = APIRouter()


@router.get("", response_model=Page[EmployeeRead], response_model_exclude_unset=True)
async def list_employees(
    actor: Annotated[User, Depends(require(Permission.EMPLOYEES_READ))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    params: Annotated[PageParams, Depends(get_page_params)],
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[EmploymentStatus | None, Query(alias="status")] = None,
    manager_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[EmployeeRead]:
    return await service.list_employees(
        actor,
        params,
        department_id=department_id,
        status=status_filter,
        manager_id=manager_id,
        search=q,
    )


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_unset=True,
)
async def create_employee(
    payload: EmployeeCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.EMPLOYEES_WRITE))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeRead:
    return await service.create_employee(actor, payload, ip_address=caller.ip_address)


@router.get(
    "/{employee_id}", response_model=EmployeeRead, response_model_exclude_unset=True
)
async def get_employee(
    employee_id: uuid.UUID,
    actor: Annotated[User, Depends(require(Permission.EMPLOYEES_READ))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeRead:
    return await service.get_employee(actor, employee_id)


@router.patch(
    "/{employee_id}", response_model=EmployeeRead, response_model_exclude_unset=True
)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.EMPLOYEES_WRITE))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeRead:
    return await service.update_employee(
        actor, employee_id, payload, ip_address=caller.ip_address
    )


@router.post(
    "/{employee_id}/terminate",
    response_model=EmployeeRead,
    response_model_exclude_unset=True,
)
async def terminate_employee(
    employee_id: uuid.UUID,
    payload: EmployeeTerminate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.EMPLOYEES_TERMINATE))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeRead:
    return await service.terminate_employee(
        actor, employee_id, payload, ip_address=caller.ip_address
    )
