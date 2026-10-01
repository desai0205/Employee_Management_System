"""Employee queries, including scope filters."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.models.employee import Employee
from app.models.enums import EmploymentStatus
from app.repositories.base import Repository, like_pattern, paginate, sort_column


class EmployeeRepository(Repository[Employee]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Employee)

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        result = await self.session.scalars(
            select(Employee).where(Employee.user_id == user_id)
        )
        return result.one_or_none()

    async def get_by_email(self, email: str) -> Employee | None:
        result = await self.session.scalars(
            select(Employee).where(Employee.email == email.lower())
        )
        return result.one_or_none()

    async def ids_for_manager(self, manager_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.session.scalars(
            select(Employee.id).where(Employee.manager_id == manager_id)
        )
        return list(result.all())

    async def list_active_ids(self) -> list[uuid.UUID]:
        result = await self.session.scalars(
            select(Employee.id).where(
                Employee.employment_status == EmploymentStatus.ACTIVE
            )
        )
        return list(result.all())

    async def count(
        self,
        visible_ids: set[uuid.UUID] | None,
        *,
        status: EmploymentStatus | None = None,
        department_id: uuid.UUID | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Employee)
        statement = self._scope(statement, visible_ids, department_id)
        if status is not None:
            statement = statement.where(Employee.employment_status == status)
        return int(await self.session.scalar(statement) or 0)

    async def count_by_status(
        self,
        visible_ids: set[uuid.UUID] | None,
        department_id: uuid.UUID | None = None,
    ) -> dict[str, int]:
        statement = select(Employee.employment_status, func.count()).group_by(
            Employee.employment_status
        )
        statement = self._scope(statement, visible_ids, department_id)
        rows = await self.session.execute(statement)
        return {status.value: count for status, count in rows.all()}

    async def count_by_department(
        self,
        visible_ids: set[uuid.UUID] | None,
        department_id: uuid.UUID | None = None,
    ) -> list[tuple[uuid.UUID, str, int]]:
        from app.models.department import Department

        statement = (
            select(Department.id, Department.name, func.count(Employee.id))
            .join(Employee, Employee.department_id == Department.id)
            .group_by(Department.id, Department.name)
            .order_by(Department.name)
        )
        statement = self._scope(statement, visible_ids, department_id)
        rows = await self.session.execute(statement)
        return [(row_id, name, count) for row_id, name, count in rows.all()]

    async def list_page(
        self,
        params: PageParams,
        *,
        visible_ids: set[uuid.UUID] | None,
        department_id: uuid.UUID | None,
        status: EmploymentStatus | None,
        manager_id: uuid.UUID | None,
        search: str | None,
    ) -> tuple[list[Employee], int, int]:
        if visible_ids is not None and not visible_ids:
            return [], 0, 0
        statement = select(Employee)
        statement = self._scope(statement, visible_ids)
        if department_id is not None:
            statement = statement.where(Employee.department_id == department_id)
        if status is not None:
            statement = statement.where(Employee.employment_status == status)
        if manager_id is not None:
            statement = statement.where(Employee.manager_id == manager_id)
        if search:
            pattern = like_pattern(search.strip())
            statement = statement.where(
                or_(
                    Employee.first_name.ilike(pattern, escape="\\"),
                    Employee.last_name.ilike(pattern, escape="\\"),
                    Employee.email.ilike(pattern, escape="\\"),
                    Employee.employee_code.ilike(pattern, escape="\\"),
                )
            )
        ordering = sort_column(
            params.sort,
            params.order,
            {
                "last_name": Employee.last_name,
                "first_name": Employee.first_name,
                "hire_date": Employee.hire_date,
                "employee_code": Employee.employee_code,
                "created_at": Employee.created_at,
            },
            default="last_name",
        )
        rows, total, pages = await paginate(self.session, statement, params, ordering)
        return rows, total, pages

    def _scope(
        self,
        statement: Any,
        visible_ids: set[uuid.UUID] | None,
        department_id: uuid.UUID | None = None,
    ) -> Any:
        if visible_ids is not None:
            statement = statement.where(Employee.id.in_(visible_ids))
        if department_id is not None:
            statement = statement.where(Employee.department_id == department_id)
        return statement
