"""Nightly token purge and missed-attendance marking."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import org_now, utc_now
from app.repositories.attendance import AttendanceRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.leave import LeaveRepository
from app.repositories.refresh_token import RefreshTokenRepository


class MaintenanceService:
    def __init__(
        self,
        tokens: RefreshTokenRepository,
        employees: EmployeeRepository,
        attendance: AttendanceRepository,
        leaves: LeaveRepository,
    ) -> None:
        self.tokens = tokens
        self.employees = employees
        self.attendance = attendance
        self.leaves = leaves

    async def purge_expired_tokens(self) -> int:
        return await self.tokens.delete_expired(utc_now())

    async def mark_missing_attendance(self) -> int:
        work_date = org_now().date() - timedelta(days=1)
        created = 0
        for employee_id in await self.employees.list_active_ids():
            existing = await self.attendance.get_for_employee_date(
                employee_id, work_date
            )
            if existing is not None or await self.leaves.approved_covers(
                employee_id, work_date
            ):
                continue
            await self.attendance.insert_absent_if_missing(
                employee_id=employee_id, work_date=work_date
            )
            created += 1
        return created


def build_maintenance_service(session: AsyncSession) -> MaintenanceService:
    return MaintenanceService(
        tokens=RefreshTokenRepository(session),
        employees=EmployeeRepository(session),
        attendance=AttendanceRepository(session),
        leaves=LeaveRepository(session),
    )
