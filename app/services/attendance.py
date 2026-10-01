"""Check-in, check-out, and HR attendance corrections."""

import uuid
from collections.abc import Callable
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import PageParams
from app.core.rbac import Permission, ensure_permission
from app.core.time import attendance_start, org_now, zone
from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.models.enums import AttendanceSource, AttendanceStatus, EmploymentStatus
from app.models.user import User
from app.repositories.attendance import AttendanceRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.errors import raise_for_integrity
from app.schemas.attendance import AttendanceCorrection, AttendanceRead
from app.schemas.common import Page
from app.services.audit import AuditService, snapshot
from app.services.scope import ScopeService

_FIELDS = [
    "id",
    "employee_id",
    "work_date",
    "check_in_at",
    "check_out_at",
    "status",
    "source",
    "note",
]


class AttendanceService:
    def __init__(
        self,
        attendance: AttendanceRepository,
        employees: EmployeeRepository,
        scope: ScopeService,
        audit: AuditService,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.attendance = attendance
        self.employees = employees
        self.scope = scope
        self.audit = audit
        self.settings = settings
        self._clock = clock or org_now

    async def check_in(self, actor: User, *, ip_address: str | None) -> AttendanceRead:
        profile = await self._self_profile(actor)
        local = self._clock().astimezone(zone(self.settings))
        existing = await self.attendance.get_for_employee_date(profile.id, local.date())
        if existing is not None:
            raise ConflictError(
                "attendance_exists", "Attendance already exists for today."
            )
        status = (
            AttendanceStatus.LATE
            if local.time() > attendance_start(self.settings)
            else AttendanceStatus.PRESENT
        )
        record = AttendanceRecord(
            id=uuid.uuid4(),
            employee_id=profile.id,
            work_date=local.date(),
            check_in_at=local,
            status=status,
            source=AttendanceSource.SELF_SERVICE,
        )
        self.attendance.add(record)
        try:
            await self.attendance.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="attendance.checked_in",
            entity_type="attendance",
            entity_id=record.id,
            after=snapshot(record, _FIELDS),
            ip_address=ip_address,
        )
        return AttendanceRead.model_validate(record)

    async def check_out(self, actor: User, *, ip_address: str | None) -> AttendanceRead:
        profile = await self._self_profile(actor)
        local = self._clock().astimezone(zone(self.settings))
        record = await self.attendance.get_for_employee_date(profile.id, local.date())
        if record is None or record.check_in_at is None:
            raise ConflictError("not_checked_in", "Check in before checking out.")
        if record.check_out_at is not None:
            raise ConflictError(
                "already_checked_out", "You have already checked out today."
            )
        if local <= record.check_in_at:
            raise ConflictError("invalid_checkout", "Check-out must be after check-in.")
        before = snapshot(record, _FIELDS)
        record.check_out_at = local
        await self.attendance.flush()
        await self.audit.record(
            actor_user_id=actor.id,
            action="attendance.checked_out",
            entity_type="attendance",
            entity_id=record.id,
            before=before,
            after=snapshot(record, _FIELDS),
            ip_address=ip_address,
        )
        return AttendanceRead.model_validate(record)

    async def list_attendance(
        self,
        actor: User,
        params: PageParams,
        *,
        employee_id: uuid.UUID | None,
        department_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        status: AttendanceStatus | None,
    ) -> Page[AttendanceRead]:
        visible = await self.scope.visible_employee_ids(actor)
        if employee_id is not None and not ScopeService.contains(visible, employee_id):
            raise ForbiddenError("You can only view attendance in your scope.")
        rows, total, pages = await self.attendance.list_page(
            params,
            visible_ids=visible,
            employee_id=employee_id,
            department_id=department_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )
        return Page(
            items=[AttendanceRead.model_validate(row) for row in rows],
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=pages,
        )

    async def correct(
        self,
        actor: User,
        attendance_id: uuid.UUID,
        payload: AttendanceCorrection,
        *,
        ip_address: str | None,
    ) -> AttendanceRead:
        ensure_permission(actor.role, Permission.ATTENDANCE_CORRECT)
        record = await self.attendance.get(attendance_id)
        if record is None:
            raise NotFoundError(
                "attendance_not_found", "Attendance record was not found."
            )
        if (
            payload.check_in_at
            and payload.check_out_at
            and payload.check_out_at <= payload.check_in_at
        ):
            raise ConflictError("invalid_checkout", "Check-out must be after check-in.")
        before = snapshot(record, _FIELDS)
        record.check_in_at = payload.check_in_at
        record.check_out_at = payload.check_out_at
        record.status = payload.status
        record.note = payload.note
        record.source = AttendanceSource.CORRECTION
        record.corrected_by_user_id = actor.id
        await self.attendance.flush()
        await self.audit.record(
            actor_user_id=actor.id,
            action="attendance.corrected",
            entity_type="attendance",
            entity_id=record.id,
            before=before,
            after=snapshot(record, _FIELDS),
            ip_address=ip_address,
        )
        return AttendanceRead.model_validate(record)

    async def _self_profile(self, actor: User) -> Employee:
        profile = await self.employees.get_by_user_id(actor.id)
        if profile is None:
            raise ConflictError(
                "employee_profile_required", "This action requires an employee profile."
            )
        if profile.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "employee_terminated", "Terminated employees cannot record attendance."
            )
        return profile
