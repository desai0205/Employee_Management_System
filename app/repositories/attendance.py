"""Attendance queries."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.models.enums import AttendanceSource, AttendanceStatus
from app.repositories.base import Repository, paginate, sort_column


class AttendanceRepository(Repository[AttendanceRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttendanceRecord)

    async def get_for_employee_date(
        self, employee_id: uuid.UUID, work_date: date
    ) -> AttendanceRecord | None:
        statement = select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_date == work_date,
        )
        result = await self.session.scalars(statement)
        return result.one_or_none()

    async def count_for_date(
        self,
        work_date: date,
        visible_ids: set[uuid.UUID] | None,
        statuses: list[AttendanceStatus],
    ) -> int:
        statement = (
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.work_date == work_date,
                AttendanceRecord.status.in_(statuses),
            )
        )
        if visible_ids is not None:
            statement = statement.where(AttendanceRecord.employee_id.in_(visible_ids))
        return int(await self.session.scalar(statement) or 0)

    async def counts_by_status(
        self,
        visible_ids: set[uuid.UUID] | None,
        date_from: date,
        date_to: date,
        department_id: uuid.UUID | None,
    ) -> dict[str, int]:
        statement = (
            select(AttendanceRecord.status, func.count())
            .where(
                AttendanceRecord.work_date >= date_from,
                AttendanceRecord.work_date <= date_to,
            )
            .group_by(AttendanceRecord.status)
        )
        if visible_ids is not None:
            statement = statement.where(AttendanceRecord.employee_id.in_(visible_ids))
        if department_id is not None:
            statement = statement.join(
                Employee, Employee.id == AttendanceRecord.employee_id
            ).where(Employee.department_id == department_id)
        rows = await self.session.execute(statement)
        return {status.value: count for status, count in rows.all()}

    async def list_page(
        self,
        params: PageParams,
        *,
        visible_ids: set[uuid.UUID] | None,
        employee_id: uuid.UUID | None,
        department_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        status: AttendanceStatus | None,
    ) -> tuple[list[AttendanceRecord], int, int]:
        if visible_ids is not None and not visible_ids:
            return [], 0, 0
        statement = select(AttendanceRecord)
        if department_id is not None:
            statement = statement.join(
                Employee, Employee.id == AttendanceRecord.employee_id
            ).where(Employee.department_id == department_id)
        if visible_ids is not None:
            statement = statement.where(AttendanceRecord.employee_id.in_(visible_ids))
        if employee_id is not None:
            statement = statement.where(AttendanceRecord.employee_id == employee_id)
        if date_from is not None:
            statement = statement.where(AttendanceRecord.work_date >= date_from)
        if date_to is not None:
            statement = statement.where(AttendanceRecord.work_date <= date_to)
        if status is not None:
            statement = statement.where(AttendanceRecord.status == status)
        ordering = sort_column(
            params.sort,
            params.order,
            {
                "work_date": AttendanceRecord.work_date,
                "status": AttendanceRecord.status,
                "created_at": AttendanceRecord.created_at,
            },
            default="work_date",
        )
        if params.sort is None:
            ordering = AttendanceRecord.work_date.desc()
        rows, total, pages = await paginate(self.session, statement, params, ordering)
        return rows, total, pages

    async def insert_absent_if_missing(
        self,
        *,
        employee_id: uuid.UUID,
        work_date: date,
    ) -> None:
        statement = (
            insert(AttendanceRecord)
            .values(
                id=uuid.uuid4(),
                employee_id=employee_id,
                work_date=work_date,
                status=AttendanceStatus.ABSENT,
                source=AttendanceSource.CORRECTION,
            )
            .on_conflict_do_nothing(constraint="uq_attendance_employee_date")
        )
        await self.session.execute(statement)
