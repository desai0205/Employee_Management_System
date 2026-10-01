"""Role-scoped dashboard counts."""

from datetime import datetime

from app.core.config import Settings
from app.core.time import zone
from app.models.enums import AttendanceStatus, EmploymentStatus, LeaveStatus
from app.models.user import User
from app.repositories.attendance import AttendanceRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.leave import LeaveRepository
from app.schemas.dashboard import DashboardRead
from app.services.scope import ScopeService

_PRESENT = [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.HALF_DAY]


class DashboardService:
    def __init__(
        self,
        employees: EmployeeRepository,
        attendance: AttendanceRepository,
        leaves: LeaveRepository,
        scope: ScopeService,
        settings: Settings,
        clock: datetime | None = None,
    ) -> None:
        self.employees = employees
        self.attendance = attendance
        self.leaves = leaves
        self.scope = scope
        self.settings = settings
        self._fixed_now = clock

    async def get_dashboard(self, actor: User) -> DashboardRead:
        visible = await self.scope.visible_employee_ids(actor)
        moment = self._fixed_now or datetime.now(zone(self.settings))
        today = moment.astimezone(zone(self.settings)).date()
        return DashboardRead(
            active_employees=await self.employees.count(
                visible, status=EmploymentStatus.ACTIVE
            ),
            employees_on_leave=await self.employees.count(
                visible, status=EmploymentStatus.ON_LEAVE
            ),
            present_today=await self.attendance.count_for_date(
                today, visible, _PRESENT
            ),
            pending_leave_requests=await self.leaves.count_requests(
                visible, LeaveStatus.PENDING
            ),
        )
