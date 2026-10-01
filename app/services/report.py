"""Headcount, attendance, and leave reports, plus queued exports."""

import uuid
from datetime import date, timedelta
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.post_commit import schedule_job
from app.core.time import org_now
from app.models.enums import ReportExportStatus, ReportType, UserRole
from app.models.report_export import ReportExport
from app.models.user import User
from app.repositories.attendance import AttendanceRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.leave import LeaveRepository
from app.repositories.report_export import ReportExportRepository
from app.repositories.user import UserRepository
from app.schemas.report import (
    AttendanceReport,
    DepartmentCount,
    HeadcountReport,
    LeaveReport,
    ReportExportCreate,
    ReportExportRead,
)
from app.services.audit import AuditService
from app.services.scope import ScopeService

logger = get_logger(__name__)


class ReportService:
    def __init__(
        self,
        employees: EmployeeRepository,
        attendance: AttendanceRepository,
        leaves: LeaveRepository,
        exports: ReportExportRepository,
        users: UserRepository,
        scope: ScopeService,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self.employees = employees
        self.attendance_records = attendance
        self.leaves = leaves
        self.exports = exports
        self.users = users
        self.scope = scope
        self.audit = audit
        self.settings = settings

    async def headcount(
        self, actor: User, department_id: uuid.UUID | None
    ) -> HeadcountReport:
        visible = await self.scope.visible_employee_ids(actor)
        by_status = await self.employees.count_by_status(visible, department_id)
        grouped = await self.employees.count_by_department(visible, department_id)
        total = sum(by_status.values())
        return HeadcountReport(
            total=total,
            by_status=by_status,
            by_department=[
                DepartmentCount(
                    department_id=item[0], department_name=item[1], count=item[2]
                )
                for item in grouped
            ],
        )

    async def attendance(
        self,
        actor: User,
        date_from: date | None,
        date_to: date | None,
        department_id: uuid.UUID | None,
    ) -> AttendanceReport:
        start, end = self._window(date_from, date_to)
        visible = await self.scope.visible_employee_ids(actor)
        counts = await self.attendance_records.counts_by_status(
            visible, start, end, department_id
        )
        return AttendanceReport(date_from=start, date_to=end, by_status=counts)

    async def leave(
        self, actor: User, date_from: date | None, date_to: date | None
    ) -> LeaveReport:
        start, end = self._window(date_from, date_to)
        visible = await self.scope.visible_employee_ids(actor)
        counts = await self.leaves.counts_by_status(visible, start, end)
        return LeaveReport(date_from=start, date_to=end, by_status=counts)

    async def request_export(
        self, actor: User, payload: ReportExportCreate, *, ip_address: str | None
    ) -> ReportExportRead:
        params = {
            "date_from": payload.date_from.isoformat() if payload.date_from else None,
            "date_to": payload.date_to.isoformat() if payload.date_to else None,
            "department_id": str(payload.department_id)
            if payload.department_id
            else None,
        }
        export = ReportExport(
            id=uuid.uuid4(),
            requester_user_id=actor.id,
            report_type=payload.report_type,
            params=params,
            status=ReportExportStatus.PENDING,
        )
        self.exports.add(export)
        await self.exports.flush()
        await self.audit.record(
            actor_user_id=actor.id,
            action="report.export_requested",
            entity_type="report_export",
            entity_id=export.id,
            after={"report_type": payload.report_type.value},
            ip_address=ip_address,
        )
        schedule_job("generate_report_export", str(export.id))
        return ReportExportRead.model_validate(export)

    async def get_export(self, actor: User, export_id: uuid.UUID) -> ReportExportRead:
        export = await self.exports.get(export_id)
        if export is None:
            raise NotFoundError(
                "report_export_not_found", "Report export was not found."
            )
        if export.requester_user_id != actor.id and actor.role != UserRole.ADMIN:
            raise ForbiddenError("You can only view your own report exports.")
        return ReportExportRead.model_validate(export)

    async def generate_export(
        self, export_id: uuid.UUID, *, final_attempt: bool
    ) -> None:
        export = await self.exports.get_for_update(export_id)
        if export is None:
            raise NotFoundError(
                "report_export_not_found", "Report export was not found."
            )
        if export.status != ReportExportStatus.PENDING:
            return
        requester = await self.users.get(export.requester_user_id)
        if requester is None:
            export.status = ReportExportStatus.FAILED
            export.error = "The requesting user no longer exists."
            return
        try:
            result = await self._build(requester, export)
            export.result = result
            export.status = ReportExportStatus.READY
            export.error = None
        except Exception:
            logger.exception("report export failed", export_id=str(export_id))
            if final_attempt:
                export.status = ReportExportStatus.FAILED
                export.error = "Report generation failed."
                return
            raise

    async def pending_export_ids(self, limit: int = 20) -> list[uuid.UUID]:
        return await self.exports.list_pending_ids(limit)

    async def process_pending(self, limit: int = 20) -> None:
        for export_id in await self.exports.list_pending_ids(limit):
            await self.generate_export(export_id, final_attempt=True)

    async def _build(self, actor: User, export: ReportExport) -> dict[str, Any]:
        department_id = (
            uuid.UUID(export.params["department_id"])
            if export.params.get("department_id")
            else None
        )
        date_from = (
            date.fromisoformat(export.params["date_from"])
            if export.params.get("date_from")
            else None
        )
        date_to = (
            date.fromisoformat(export.params["date_to"])
            if export.params.get("date_to")
            else None
        )
        if export.report_type == ReportType.HEADCOUNT:
            return (await self.headcount(actor, department_id)).model_dump(mode="json")
        if export.report_type == ReportType.ATTENDANCE:
            return (
                await self.attendance(actor, date_from, date_to, department_id)
            ).model_dump(mode="json")
        return (await self.leave(actor, date_from, date_to)).model_dump(mode="json")

    def _window(
        self, date_from: date | None, date_to: date | None
    ) -> tuple[date, date]:
        today = org_now(self.settings).date()
        end = date_to or today
        start = date_from or (end - timedelta(days=30))
        return start, end
