"""Who a caller can see: the whole organization, their direct reports, or themselves."""

import uuid

from app.models.enums import UserRole
from app.models.user import User
from app.repositories.employee import EmployeeRepository


class ScopeService:
    def __init__(self, employees: EmployeeRepository) -> None:
        self.employees = employees

    async def visible_employee_ids(self, actor: User) -> set[uuid.UUID] | None:
        """None means every employee. An empty set means the caller has no profile."""
        if actor.role in (UserRole.ADMIN, UserRole.HR):
            return None
        profile = await self.employees.get_by_user_id(actor.id)
        if profile is None:
            return set()
        if actor.role == UserRole.EMPLOYEE:
            return {profile.id}
        report_ids = await self.employees.ids_for_manager(profile.id)
        return {profile.id, *report_ids}

    @staticmethod
    def contains(visible_ids: set[uuid.UUID] | None, employee_id: uuid.UUID) -> bool:
        return visible_ids is None or employee_id in visible_ids
