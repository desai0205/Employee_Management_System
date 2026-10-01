"""Helpers for building persistent rows inside integration tests."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import EmploymentStatus, UserRole
from app.models.user import User


async def make_user(
    session: AsyncSession, email: str, role: UserRole, password: str = "Password1"
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def make_department(session: AsyncSession, code: str = "ENG") -> Department:
    department = Department(id=uuid.uuid4(), name=f"Dept {code}", code=code)
    session.add(department)
    await session.flush()
    return department


async def make_employee(
    session: AsyncSession,
    department: Department,
    *,
    code: str,
    email: str,
    user: User | None = None,
    manager_id: uuid.UUID | None = None,
) -> Employee:
    employee = Employee(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        employee_code=code,
        first_name="Ada",
        last_name=code,
        email=email.lower(),
        department_id=department.id,
        manager_id=manager_id,
        job_title="Engineer",
        employment_status=EmploymentStatus.ACTIVE,
        hire_date=date(2024, 1, 1),
        currency="USD",
    )
    session.add(employee)
    await session.flush()
    return employee
