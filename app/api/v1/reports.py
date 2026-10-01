"""Report routes."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Caller, get_caller, get_report_service, require
from app.core.rbac import Permission
from app.models.user import User
from app.schemas.report import (
    AttendanceReport,
    HeadcountReport,
    LeaveReport,
    ReportExportCreate,
    ReportExportRead,
)
from app.services.report import ReportService

router = APIRouter()


@router.get("/headcount", response_model=HeadcountReport)
async def headcount_report(
    actor: Annotated[User, Depends(require(Permission.REPORTS_READ))],
    service: Annotated[ReportService, Depends(get_report_service)],
    department_id: Annotated[uuid.UUID | None, Query()] = None,
) -> HeadcountReport:
    return await service.headcount(actor, department_id)


@router.get("/attendance", response_model=AttendanceReport)
async def attendance_report(
    actor: Annotated[User, Depends(require(Permission.REPORTS_READ))],
    service: Annotated[ReportService, Depends(get_report_service)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AttendanceReport:
    return await service.attendance(actor, date_from, date_to, department_id)


@router.get("/leave", response_model=LeaveReport)
async def leave_report(
    actor: Annotated[User, Depends(require(Permission.REPORTS_READ))],
    service: Annotated[ReportService, Depends(get_report_service)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> LeaveReport:
    return await service.leave(actor, date_from, date_to)


@router.post(
    "/exports", response_model=ReportExportRead, status_code=status.HTTP_202_ACCEPTED
)
async def create_export(
    payload: ReportExportCreate,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(require(Permission.REPORTS_READ))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportExportRead:
    return await service.request_export(actor, payload, ip_address=caller.ip_address)


@router.get("/exports/{export_id}", response_model=ReportExportRead)
async def get_export(
    export_id: uuid.UUID,
    actor: Annotated[User, Depends(require(Permission.REPORTS_READ))],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportExportRead:
    return await service.get_export(actor, export_id)
