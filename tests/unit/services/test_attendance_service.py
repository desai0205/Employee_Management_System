"""Attendance check-in status depends on the organization start time."""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.models.enums import EmploymentStatus, UserRole
from app.models.user import User
from app.services.attendance import AttendanceService
from app.services.scope import ScopeService


class Employees:
    def __init__(self, row: Employee) -> None:
        self.row = row

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        return self.row if self.row.user_id == user_id else None

    async def ids_for_manager(self, _manager_id: uuid.UUID) -> list[uuid.UUID]:
        return []


class Attendance:
    def __init__(self) -> None:
        self.rows: list[AttendanceRecord] = []

    def add(self, record: AttendanceRecord) -> AttendanceRecord:
        self.rows.append(record)
        return record

    async def flush(self) -> None:
        return None

    async def get_for_employee_date(
        self, employee_id: uuid.UUID, work_date: date
    ) -> AttendanceRecord | None:
        return next(
            (
                row
                for row in self.rows
                if row.employee_id == employee_id and row.work_date == work_date
            ),
            None,
        )


class Audit:
    async def record(self, **_kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_check_in_is_late_after_the_start_time_and_cannot_repeat() -> None:
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        password_hash="x",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    profile = Employee(
        id=uuid.uuid4(),
        user_id=user.id,
        employee_code="ADA",
        first_name="Ada",
        last_name="Lovelace",
        email=user.email,
        department_id=uuid.uuid4(),
        job_title="Engineer",
        employment_status=EmploymentStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        currency="USD",
    )
    attendance = Attendance()
    employees = Employees(profile)
    settings = Settings(
        app_env="local",
        secret_key="unit-test-secret-key-32-characters",
        org_timezone="UTC",
        attendance_start_time="09:15",
    )

    def late_clock() -> datetime:
        return datetime(2026, 4, 1, 9, 30, tzinfo=UTC)

    service = AttendanceService(
        attendance,  # type: ignore[arg-type]
        employees,  # type: ignore[arg-type]
        ScopeService(employees),  # type: ignore[arg-type]
        Audit(),  # type: ignore[arg-type]
        settings,
        clock=late_clock,
    )
    record = await service.check_in(user, ip_address=None)
    assert record.status.value == "late"
    with pytest.raises(ConflictError) as caught:
        await service.check_in(user, ip_address=None)
    assert caught.value.code == "attendance_exists"
