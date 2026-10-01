"""Leave balance and overlap rules."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import ConflictError, ForbiddenError
from app.models.employee import Employee
from app.models.enums import EmploymentStatus, LeaveStatus, UserRole
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.models.user import User
from app.schemas.leave import LeaveDecision, LeaveRequestCreate
from app.services.leave import LeaveService, count_weekdays
from app.services.scope import ScopeService


class Employees:
    def __init__(self, rows: list[Employee]) -> None:
        self.rows = {row.id: row for row in rows}

    async def get(self, employee_id: uuid.UUID) -> Employee | None:
        return self.rows.get(employee_id)

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        return next((row for row in self.rows.values() if row.user_id == user_id), None)

    async def ids_for_manager(self, manager_id: uuid.UUID) -> list[uuid.UUID]:
        return [row.id for row in self.rows.values() if row.manager_id == manager_id]


class Leaves:
    def __init__(self, balance: LeaveBalance, leave_type: LeaveType) -> None:
        self.balance = balance
        self.leave_type = leave_type
        self.requests: list[LeaveRequest] = []

    async def get_type(self, leave_type_id: uuid.UUID) -> LeaveType | None:
        return self.leave_type if self.leave_type.id == leave_type_id else None

    async def has_overlap(
        self,
        employee_id: uuid.UUID,
        start: date,
        end: date,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        return any(
            row.employee_id == employee_id
            and row.status in (LeaveStatus.PENDING, LeaveStatus.APPROVED)
            and row.start_date <= end
            and row.end_date >= start
            and row.id != exclude_id
            for row in self.requests
        )

    async def get_balance_for_update(
        self, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> LeaveBalance | None:
        if (
            self.balance.employee_id == employee_id
            and self.balance.leave_type_id == leave_type_id
            and self.balance.year == year
        ):
            return self.balance
        return None

    async def sum_pending_days(
        self, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> Decimal:
        return sum(
            (
                row.days
                for row in self.requests
                if row.employee_id == employee_id
                and row.leave_type_id == leave_type_id
                and row.status == LeaveStatus.PENDING
                and row.start_date.year == year
            ),
            Decimal("0"),
        )

    def add(self, request: LeaveRequest) -> LeaveRequest:
        self.requests.append(request)
        return request

    async def flush(self) -> None:
        return None

    async def get(self, request_id: uuid.UUID) -> LeaveRequest | None:
        return next((row for row in self.requests if row.id == request_id), None)


class Audit:
    async def record(self, **_kwargs: object) -> None:
        return None


def profile(user: User, manager_id: uuid.UUID | None = None) -> Employee:
    return Employee(
        id=uuid.uuid4(),
        user_id=user.id,
        employee_code=user.email[:8].upper(),
        first_name="Ada",
        last_name="Lovelace",
        email=user.email,
        department_id=uuid.uuid4(),
        manager_id=manager_id,
        job_title="Engineer",
        employment_status=EmploymentStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        currency="USD",
    )


def test_weekday_count_skips_the_weekend() -> None:
    assert count_weekdays(date(2026, 1, 5), date(2026, 1, 11)) == Decimal(5)


@pytest.mark.asyncio
async def test_request_rejects_overlap_and_insufficient_balance() -> None:
    staff = User(
        id=uuid.uuid4(),
        email="staff@example.com",
        password_hash="x",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    manager_user = User(
        id=uuid.uuid4(),
        email="manager@example.com",
        password_hash="x",
        role=UserRole.MANAGER,
        is_active=True,
    )
    manager = profile(manager_user)
    worker = profile(staff, manager_id=manager.id)
    leave_type = LeaveType(
        id=uuid.uuid4(),
        name="Annual",
        code="ANN",
        default_annual_days=Decimal("5.0"),
        is_paid=True,
        is_active=True,
    )
    balance = LeaveBalance(
        employee_id=worker.id,
        leave_type_id=leave_type.id,
        year=2026,
        allocated_days=Decimal("5.0"),
        used_days=Decimal("0.0"),
    )
    employees = Employees([manager, worker])
    leaves = Leaves(balance, leave_type)
    service = LeaveService(leaves, employees, ScopeService(employees), Audit())  # type: ignore[arg-type]
    created = await service.request_leave(
        staff,
        LeaveRequestCreate(
            leave_type_id=leave_type.id,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
            reason="Rest",
        ),
        ip_address=None,
    )
    assert created.days == Decimal(5)
    with pytest.raises(ConflictError) as overlap:
        await service.request_leave(
            staff,
            LeaveRequestCreate(
                leave_type_id=leave_type.id,
                start_date=date(2026, 1, 8),
                end_date=date(2026, 1, 8),
                reason="Again",
            ),
            ip_address=None,
        )
    assert overlap.value.code == "leave_overlap"
    approved = await service.approve(
        manager_user, created.id, LeaveDecision(note="ok"), ip_address=None
    )
    assert approved.status == LeaveStatus.APPROVED
    assert balance.used_days == Decimal(5)
    with pytest.raises(ForbiddenError):
        await service.approve(staff, created.id, LeaveDecision(), ip_address=None)
