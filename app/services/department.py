"""Department rules, including manager assignment."""

import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.models.department import Department
from app.models.enums import EmploymentStatus
from app.models.user import User
from app.repositories.department import DepartmentRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.errors import raise_for_integrity
from app.schemas.common import Page
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.audit import AuditService, snapshot

_FIELDS = ["id", "name", "code", "description", "manager_id"]


class DepartmentService:
    def __init__(
        self,
        departments: DepartmentRepository,
        employees: EmployeeRepository,
        audit: AuditService,
    ) -> None:
        self.departments = departments
        self.employees = employees
        self.audit = audit

    async def list_departments(self, params: PageParams) -> Page[DepartmentRead]:
        rows, total, pages = await self.departments.list_page(params)
        return Page(
            items=[DepartmentRead.model_validate(row) for row in rows],
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=pages,
        )

    async def get_department(self, department_id: uuid.UUID) -> DepartmentRead:
        department = await self._get(department_id)
        return DepartmentRead.model_validate(department)

    async def create_department(
        self,
        actor: User,
        payload: DepartmentCreate,
        *,
        ip_address: str | None,
    ) -> DepartmentRead:
        if payload.manager_id is not None:
            raise ConflictError(
                "manager_assigned_later",
                "Create the department first, then assign a manager who belongs to it.",
            )
        department = Department(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            code=payload.code,
            description=payload.description,
        )
        self.departments.add(department)
        try:
            await self.departments.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="department.created",
            entity_type="department",
            entity_id=department.id,
            after=snapshot(department, _FIELDS),
            ip_address=ip_address,
        )
        return DepartmentRead.model_validate(department)

    async def update_department(
        self,
        actor: User,
        department_id: uuid.UUID,
        payload: DepartmentUpdate,
        *,
        ip_address: str | None,
    ) -> DepartmentRead:
        department = await self._get(department_id)
        before = snapshot(department, _FIELDS)
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is not None:
            department.name = str(changes["name"]).strip()
        if "description" in changes:
            department.description = changes["description"]
        if "manager_id" in changes:
            await self._assign_manager(department, changes["manager_id"])
        try:
            await self.departments.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="department.updated",
            entity_type="department",
            entity_id=department.id,
            before=before,
            after=snapshot(department, _FIELDS),
            ip_address=ip_address,
        )
        return DepartmentRead.model_validate(department)

    async def _assign_manager(
        self, department: Department, manager_id: uuid.UUID | None
    ) -> None:
        if manager_id is None:
            department.manager_id = None
            return
        manager = await self.employees.get(manager_id)
        if manager is None:
            raise NotFoundError("manager_not_found", "Manager was not found.")
        if manager.department_id != department.id:
            raise ConflictError(
                "invalid_manager",
                "The department manager must belong to that department.",
            )
        if manager.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "invalid_manager", "A terminated employee cannot manage a department."
            )
        department.manager_id = manager.id

    async def _get(self, department_id: uuid.UUID) -> Department:
        department = await self.departments.get(department_id)
        if department is None:
            raise NotFoundError("department_not_found", "Department was not found.")
        return department
