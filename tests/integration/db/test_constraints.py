"""Database uniqueness and foreign-key constraints."""

import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import get_session_factory
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceSource, AttendanceStatus, UserRole
from tests.factories import make_department, make_employee, make_user


def test_attendance_is_unique_per_employee_and_day(
    database_urls: tuple[str, str],
) -> None:
    async def run() -> None:
        factory = get_session_factory()
        async with factory() as session:
            department = await make_department(session, "QA")
            employee = await make_employee(
                session, department, code="QA1", email="qa@example.com"
            )
            await make_user(session, "unused@example.com", UserRole.EMPLOYEE)
            session.add(
                AttendanceRecord(
                    id=uuid.uuid4(),
                    employee_id=employee.id,
                    work_date=date(2026, 5, 4),
                    status=AttendanceStatus.PRESENT,
                    source=AttendanceSource.SELF_SERVICE,
                )
            )
            await session.flush()
            session.add(
                AttendanceRecord(
                    id=uuid.uuid4(),
                    employee_id=employee.id,
                    work_date=date(2026, 5, 4),
                    status=AttendanceStatus.ABSENT,
                    source=AttendanceSource.CORRECTION,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

    asyncio.run(run())
