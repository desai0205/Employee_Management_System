"""Attendance routes."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    Caller,
    get_attendance_service,
    get_caller,
    get_page_params,
    require,
)
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.models.enums import AttendanceStatus
from app.models.user import User
from app.schemas.attendance import AttendanceCorrection, AttendanceRead
from app.schemas.common import Page
from app.services.attendance import AttendanceService

router = APIRouter()


@router.post("/check-in", response_model=AttendanceRead)
async def check_in(
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.ATTENDANCE_SELF))],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceRead:
    return await service.check_in(actor, ip_address=caller.ip_address)


@router.post("/check-out", response_model=AttendanceRead)
async def check_out(
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.ATTENDANCE_SELF))],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceRead:
    return await service.check_out(actor, ip_address=caller.ip_address)


@router.get("", response_model=Page[AttendanceRead])
async def list_attendance(
    actor: Annotated[User, Depends(require(Permission.ATTENDANCE_READ))],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
    params: Annotated[PageParams, Depends(get_page_params)],
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    status_filter: Annotated[AttendanceStatus | None, Query(alias="status")] = None,
) -> Page[AttendanceRead]:
    return await service.list_attendance(
        actor,
        params,
        employee_id=employee_id,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
    )


@router.patch("/{attendance_id}", response_model=AttendanceRead)
async def correct_attendance(
    attendance_id: uuid.UUID,
    payload: AttendanceCorrection,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.ATTENDANCE_CORRECT))],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceRead:
    return await service.correct(
        actor, attendance_id, payload, ip_address=caller.ip_address
    )
