"""Employee visibility and compensation fields."""

import uuid
from datetime import date

import pytest

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.core.pagination import PageParams
from app.models.employee import Employee
from app.models.enums import EmploymentStatus, UserRole
from app.models.user import User
from app.services.employee import EmployeeService
from app.services.scope import ScopeService


def employee(
    user_id: uuid.UUID, manager_id: uuid.UUID | None = None, salary: int | None = 100_00
) -> Employee:
    return Employee(
        id=uuid.uuid4(),
        user_id=user_id,
        employee_code=uuid.uuid4().hex[:8].upper(),
        first_name="Ada",
        last_name="Lovelace",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        department_id=uuid.uuid4(),
        manager_id=manager_id,
        job_title="Engineer",
        employment_status=EmploymentStatus.ACTIVE,
        hire_date=date(2024, 1, 2),
        salary_cents=salary,
        currency="USD",
    )


class Employees:
    def __init__(self, rows: list[Employee]) -> None:
        self.rows = {row.id: row for row in rows}

    async def get(self, employee_id: uuid.UUID) -> Employee | None:
        return self.rows.get(employee_id)

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        return next((row for row in self.rows.values() if row.user_id == user_id), None)

    async def ids_for_manager(self, manager_id: uuid.UUID) -> list[uuid.UUID]:
        return [row.id for row in self.rows.values() if row.manager_id == manager_id]

    async def list_page(
        self, params: PageParams, **kwargs: object
    ) -> tuple[list[Employee], int, int]:
        visible = kwargs["visible_ids"]
        rows = list(self.rows.values())
        if isinstance(visible, set):
            rows = [row for row in rows if row.id in visible]
        return rows, len(rows), 1


def service(rows: list[Employee]) -> EmployeeService:
    repository = Employees(rows)
    settings = Settings(
        app_env="local",
        secret_key="unit-test-secret-key-32-characters",
        default_currency="USD",
    )
    return EmployeeService(
        repository,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        ScopeService(repository),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        settings,
    )


@pytest.mark.asyncio
async def test_manager_cannot_read_outside_the_team_and_cannot_see_salary() -> None:
    manager_user = User(
        id=uuid.uuid4(),
        email="mgr@example.com",
        password_hash="x",
        role=UserRole.MANAGER,
        is_active=True,
    )
    staff_user = User(
        id=uuid.uuid4(),
        email="staff@example.com",
        password_hash="x",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    outsider_user = User(
        id=uuid.uuid4(),
        email="out@example.com",
        password_hash="x",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    manager = employee(manager_user.id)
    report = employee(staff_user.id, manager_id=manager.id)
    outsider = employee(outsider_user.id)
    built = service([manager, report, outsider])

    async def run() -> None:
        seen = await built.get_employee(manager_user, report.id)
        assert seen.id == report.id
        assert "salary_cents" not in seen.model_dump(exclude_unset=True)
        with pytest.raises(ForbiddenError):
            await built.get_employee(manager_user, outsider.id)
        admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            password_hash="x",
            role=UserRole.ADMIN,
            is_active=True,
        )
        admin_view = await built.get_employee(admin, outsider.id)
        assert admin_view.model_dump(exclude_unset=True)["salary_cents"] == 100_00

    await run()
