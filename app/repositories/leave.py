"""Leave type, balance, and request queries."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.models.enums import LeaveStatus
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.repositories.base import Repository, paginate, sort_column


class LeaveRepository(Repository[LeaveRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LeaveRequest)

    async def add_type(self, leave_type: LeaveType) -> LeaveType:
        self.session.add(leave_type)
        await self.session.flush()
        return leave_type

    async def get_type(self, leave_type_id: uuid.UUID) -> LeaveType | None:
        return await self.session.get(LeaveType, leave_type_id)

    async def list_types(self, *, active_only: bool) -> list[LeaveType]:
        statement = select(LeaveType).order_by(LeaveType.name)
        if active_only:
            statement = statement.where(LeaveType.is_active.is_(True))
        result = await self.session.scalars(statement)
        return list(result.all())

    async def add_balance(self, balance: LeaveBalance) -> LeaveBalance:
        self.session.add(balance)
        await self.session.flush()
        return balance

    async def get_balance_for_update(
        self,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        year: int,
    ) -> LeaveBalance | None:
        statement = (
            select(LeaveBalance)
            .where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.year == year,
            )
            .with_for_update()
        )
        result = await self.session.scalars(statement)
        return result.one_or_none()

    async def list_balances(
        self,
        visible_ids: set[uuid.UUID] | None,
        *,
        employee_id: uuid.UUID | None,
        year: int | None,
    ) -> list[LeaveBalance]:
        if visible_ids is not None and not visible_ids:
            return []
        statement = select(LeaveBalance).order_by(LeaveBalance.year.desc())
        if visible_ids is not None:
            statement = statement.where(LeaveBalance.employee_id.in_(visible_ids))
        if employee_id is not None:
            statement = statement.where(LeaveBalance.employee_id == employee_id)
        if year is not None:
            statement = statement.where(LeaveBalance.year == year)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def sum_pending_days(
        self,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        year: int,
    ) -> Decimal:
        statement = select(func.coalesce(func.sum(LeaveRequest.days), 0)).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_type_id == leave_type_id,
            LeaveRequest.status == LeaveStatus.PENDING,
            func.extract("year", LeaveRequest.start_date) == year,
        )
        value = await self.session.scalar(statement)
        return Decimal(value or 0)

    async def has_overlap(
        self,
        employee_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        statement = (
            select(func.count())
            .select_from(LeaveRequest)
            .where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_((LeaveStatus.PENDING, LeaveStatus.APPROVED)),
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
        )
        if exclude_id is not None:
            statement = statement.where(LeaveRequest.id != exclude_id)
        return int(await self.session.scalar(statement) or 0) > 0

    async def approved_covers(self, employee_id: uuid.UUID, work_date: date) -> bool:
        statement = (
            select(func.count())
            .select_from(LeaveRequest)
            .where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= work_date,
                LeaveRequest.end_date >= work_date,
            )
        )
        return int(await self.session.scalar(statement) or 0) > 0

    async def count_requests(
        self, visible_ids: set[uuid.UUID] | None, status: LeaveStatus | None
    ) -> int:
        statement = select(func.count()).select_from(LeaveRequest)
        statement = self._scope(statement, visible_ids)
        if status is not None:
            statement = statement.where(LeaveRequest.status == status)
        return int(await self.session.scalar(statement) or 0)

    async def counts_by_status(
        self,
        visible_ids: set[uuid.UUID] | None,
        date_from: date,
        date_to: date,
    ) -> dict[str, int]:
        statement = (
            select(LeaveRequest.status, func.count())
            .where(
                or_(
                    and_(
                        LeaveRequest.start_date >= date_from,
                        LeaveRequest.start_date <= date_to,
                    ),
                    and_(
                        LeaveRequest.end_date >= date_from,
                        LeaveRequest.end_date <= date_to,
                    ),
                )
            )
            .group_by(LeaveRequest.status)
        )
        statement = self._scope(statement, visible_ids)
        rows = await self.session.execute(statement)
        return {status.value: count for status, count in rows.all()}

    async def list_page(
        self,
        params: PageParams,
        *,
        visible_ids: set[uuid.UUID] | None,
        employee_id: uuid.UUID | None,
        status: LeaveStatus | None,
        leave_type_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[list[LeaveRequest], int, int]:
        if visible_ids is not None and not visible_ids:
            return [], 0, 0
        statement = select(LeaveRequest)
        statement = self._scope(statement, visible_ids)
        if employee_id is not None:
            statement = statement.where(LeaveRequest.employee_id == employee_id)
        if status is not None:
            statement = statement.where(LeaveRequest.status == status)
        if leave_type_id is not None:
            statement = statement.where(LeaveRequest.leave_type_id == leave_type_id)
        if date_from is not None:
            statement = statement.where(LeaveRequest.end_date >= date_from)
        if date_to is not None:
            statement = statement.where(LeaveRequest.start_date <= date_to)
        ordering = sort_column(
            params.sort,
            params.order,
            {
                "start_date": LeaveRequest.start_date,
                "created_at": LeaveRequest.created_at,
                "status": LeaveRequest.status,
            },
            default="created_at",
        )
        if params.sort is None:
            ordering = LeaveRequest.created_at.desc()
        rows, total, pages = await paginate(self.session, statement, params, ordering)
        return rows, total, pages

    def _scope(self, statement: Any, visible_ids: set[uuid.UUID] | None) -> Any:
        if visible_ids is None:
            return statement
        return statement.where(LeaveRequest.employee_id.in_(visible_ids))
