"""Leave type, balance, and request routes."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Caller, get_caller, get_leave_service, get_page_params, require
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.models.enums import LeaveStatus
from app.models.user import User
from app.schemas.common import Page
from app.schemas.leave import (
    LeaveBalanceCreate,
    LeaveBalanceRead,
    LeaveDecision,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveTypeCreate,
    LeaveTypeRead,
)
from app.services.leave import LeaveService

router = APIRouter()
types_router = APIRouter()
balances_router = APIRouter()


@types_router.get("", response_model=list[LeaveTypeRead])
async def list_leave_types(
    _actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
    active_only: Annotated[bool, Query()] = True,
) -> list[LeaveTypeRead]:
    return await service.list_types(active_only=active_only)


@types_router.post(
    "", response_model=LeaveTypeRead, status_code=status.HTTP_201_CREATED
)
async def create_leave_type(
    payload: LeaveTypeCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_MANAGE))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveTypeRead:
    return await service.create_type(actor, payload, ip_address=caller.ip_address)


@balances_router.get("", response_model=list[LeaveBalanceRead])
async def list_balances(
    actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> list[LeaveBalanceRead]:
    return await service.list_balances(actor, employee_id=employee_id, year=year)


@balances_router.post(
    "", response_model=LeaveBalanceRead, status_code=status.HTTP_201_CREATED
)
async def allocate_balance(
    payload: LeaveBalanceCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_MANAGE))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveBalanceRead:
    return await service.allocate(actor, payload, ip_address=caller.ip_address)


@router.get("", response_model=Page[LeaveRequestRead])
async def list_leaves(
    actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
    params: Annotated[PageParams, Depends(get_page_params)],
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[LeaveStatus | None, Query(alias="status")] = None,
    leave_type_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Page[LeaveRequestRead]:
    return await service.list_requests(
        actor,
        params,
        employee_id=employee_id,
        status=status_filter,
        leave_type_id=leave_type_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=LeaveRequestRead, status_code=status.HTTP_201_CREATED)
async def request_leave(
    payload: LeaveRequestCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveRequestRead:
    return await service.request_leave(actor, payload, ip_address=caller.ip_address)


@router.get("/{leave_id}", response_model=LeaveRequestRead)
async def get_leave(
    leave_id: uuid.UUID,
    actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveRequestRead:
    return await service.get_request(actor, leave_id)


@router.post("/{leave_id}/approve", response_model=LeaveRequestRead)
async def approve_leave(
    leave_id: uuid.UUID,
    payload: LeaveDecision,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_APPROVE))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveRequestRead:
    return await service.approve(actor, leave_id, payload, ip_address=caller.ip_address)


@router.post("/{leave_id}/reject", response_model=LeaveRequestRead)
async def reject_leave(
    leave_id: uuid.UUID,
    payload: LeaveDecision,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_APPROVE))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveRequestRead:
    return await service.reject(actor, leave_id, payload, ip_address=caller.ip_address)


@router.post("/{leave_id}/cancel", response_model=LeaveRequestRead)
async def cancel_leave(
    leave_id: uuid.UUID,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.LEAVE_REQUEST))],
    service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveRequestRead:
    return await service.cancel(actor, leave_id, ip_address=caller.ip_address)
