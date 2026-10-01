"""Department queries."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.models.department import Department
from app.repositories.base import Repository, paginate, sort_column


class DepartmentRepository(Repository[Department]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Department)

    async def get_by_code(self, code: str) -> Department | None:
        result = await self.session.scalars(
            select(Department).where(Department.code == code)
        )
        return result.one_or_none()

    async def list_page(self, params: PageParams) -> tuple[list[Department], int, int]:
        statement = select(Department)
        ordering = sort_column(
            params.sort,
            params.order,
            {
                "name": Department.name,
                "code": Department.code,
                "created_at": Department.created_at,
            },
            default="name",
        )
        rows, total, pages = await paginate(self.session, statement, params, ordering)
        return rows, total, pages

    async def get(self, entity_id: uuid.UUID) -> Department | None:
        return await self.session.get(Department, entity_id)
