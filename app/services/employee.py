"""Employee lifecycle. Scope and compensation visibility are enforced here."""

import uuid

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import PageParams
from app.core.rbac import Permission, role_allows
from app.core.security import hash_password
from app.models.employee import Employee
from app.models.enums import EmploymentStatus, UserRole
from app.models.user import User
from app.repositories.department import DepartmentRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.errors import raise_for_integrity
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeRead,
    EmployeeTerminate,
    EmployeeUpdate,
)
from app.services.audit import AuditService, snapshot
from app.services.scope import ScopeService

_PUBLIC_FIELDS = [
    "id",
    "user_id",
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "phone",
    "department_id",
    "manager_id",
    "job_title",
    "employment_status",
    "hire_date",
    "termination_date",
]


class EmployeeService:
    def __init__(
        self,
        employees: EmployeeRepository,
        users: UserRepository,
        departments: DepartmentRepository,
        scope: ScopeService,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self.employees = employees
        self.users = users
        self.departments = departments
        self.scope = scope
        self.audit = audit
        self.settings = settings

    async def list_employees(
        self,
        actor: User,
        params: PageParams,
        *,
        department_id: uuid.UUID | None,
        status: EmploymentStatus | None,
        manager_id: uuid.UUID | None,
        search: str | None,
    ) -> Page[EmployeeRead]:
        visible = await self.scope.visible_employee_ids(actor)
        rows, total, pages = await self.employees.list_page(
            params,
            visible_ids=visible,
            department_id=department_id,
            status=status,
            manager_id=manager_id,
            search=search,
        )
        include_salary = role_allows(actor.role, Permission.EMPLOYEES_COMPENSATION)
        return Page(
            items=[self._read(row, include_salary=include_salary) for row in rows],
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=pages,
        )

    async def get_employee(self, actor: User, employee_id: uuid.UUID) -> EmployeeRead:
        employee = await self._visible_employee(actor, employee_id)
        return self._read(
            employee,
            include_salary=role_allows(actor.role, Permission.EMPLOYEES_COMPENSATION),
        )

    async def create_employee(
        self, actor: User, payload: EmployeeCreate, *, ip_address: str | None
    ) -> EmployeeRead:
        if (
            payload.account_password is not None
            and actor.role == UserRole.HR
            and payload.account_role not in (UserRole.EMPLOYEE, UserRole.MANAGER)
        ):
            raise ForbiddenError("HR can only create employee or manager accounts.")
        department = await self.departments.get(payload.department_id)
        if department is None:
            raise NotFoundError("department_not_found", "Department was not found.")
        if payload.manager_id is not None:
            await self._require_active_manager(payload.manager_id)
        try:
            user_id = await self._maybe_create_user(payload)
            employee = Employee(
                id=uuid.uuid4(),
                user_id=user_id,
                employee_code=payload.employee_code,
                first_name=payload.first_name.strip(),
                last_name=payload.last_name.strip(),
                email=str(payload.email).lower(),
                phone=payload.phone,
                department_id=payload.department_id,
                manager_id=payload.manager_id,
                job_title=payload.job_title.strip(),
                employment_status=EmploymentStatus.ACTIVE,
                hire_date=payload.hire_date,
                salary_cents=payload.salary_cents,
                currency=(payload.currency or self.settings.default_currency).upper(),
            )
            self.employees.add(employee)
            await self.employees.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="employee.created",
            entity_type="employee",
            entity_id=employee.id,
            after=self._audit_snapshot(employee, actor),
            ip_address=ip_address,
        )
        return self._read(employee, include_salary=True)

    async def update_employee(
        self,
        actor: User,
        employee_id: uuid.UUID,
        payload: EmployeeUpdate,
        *,
        ip_address: str | None,
    ) -> EmployeeRead:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee_not_found", "Employee was not found.")
        if employee.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "employee_terminated", "Terminated employees cannot be edited."
            )
        before = self._audit_snapshot(employee, actor)
        changes = payload.model_dump(exclude_unset=True)
        if "manager_id" in changes and changes["manager_id"] == employee.id:
            raise ConflictError(
                "invalid_manager", "An employee cannot be their own manager."
            )
        if changes.get("manager_id") is not None:
            await self._require_active_manager(changes["manager_id"])
        if "department_id" in changes:
            department = await self.departments.get(changes["department_id"])
            if department is None:
                raise NotFoundError("department_not_found", "Department was not found.")
        if "email" in changes and changes["email"] is not None:
            changes["email"] = str(changes["email"]).lower()
        if "currency" in changes and changes["currency"] is not None:
            changes["currency"] = str(changes["currency"]).upper()
        for field, value in changes.items():
            setattr(
                employee,
                field,
                value.strip()
                if isinstance(value, str)
                and field in {"first_name", "last_name", "job_title"}
                else value,
            )
        if employee.user_id is not None and "email" in changes:
            account = await self.users.get(employee.user_id)
            if account is not None:
                account.email = employee.email
        try:
            await self.employees.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="employee.updated",
            entity_type="employee",
            entity_id=employee.id,
            before=before,
            after=self._audit_snapshot(employee, actor),
            ip_address=ip_address,
        )
        return self._read(employee, include_salary=True)

    async def terminate_employee(
        self,
        actor: User,
        employee_id: uuid.UUID,
        payload: EmployeeTerminate,
        *,
        ip_address: str | None,
    ) -> EmployeeRead:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee_not_found", "Employee was not found.")
        if employee.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "employee_terminated", "Employee is already terminated."
            )
        if payload.termination_date < employee.hire_date:
            raise ConflictError(
                "invalid_termination_date",
                "Termination date cannot be before the hire date.",
            )
        before = self._audit_snapshot(employee, actor)
        employee.employment_status = EmploymentStatus.TERMINATED
        employee.termination_date = payload.termination_date
        if employee.user_id is not None:
            account = await self.users.get(employee.user_id)
            if account is not None:
                account.is_active = False
        await self.employees.flush()
        await self.audit.record(
            actor_user_id=actor.id,
            action="employee.terminated",
            entity_type="employee",
            entity_id=employee.id,
            before=before,
            after=self._audit_snapshot(employee, actor),
            ip_address=ip_address,
        )
        return self._read(employee, include_salary=True)

    async def _visible_employee(self, actor: User, employee_id: uuid.UUID) -> Employee:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee_not_found", "Employee was not found.")
        visible = await self.scope.visible_employee_ids(actor)
        if not self.scope.contains(visible, employee.id):
            raise ForbiddenError("You can only view employees in your scope.")
        return employee

    async def _require_active_manager(self, manager_id: uuid.UUID) -> Employee:
        manager = await self.employees.get(manager_id)
        if manager is None:
            raise NotFoundError("manager_not_found", "Manager was not found.")
        if manager.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "invalid_manager", "A terminated employee cannot be a manager."
            )
        return manager

    async def _maybe_create_user(self, payload: EmployeeCreate) -> uuid.UUID | None:
        if payload.account_password is None:
            return None
        user = User(
            id=uuid.uuid4(),
            email=str(payload.email).lower(),
            password_hash=hash_password(payload.account_password),
            role=payload.account_role,
            is_active=True,
        )
        self.users.add(user)
        await self.users.flush()
        return user.id

    def _read(self, employee: Employee, *, include_salary: bool) -> EmployeeRead:
        data = snapshot(employee, _PUBLIC_FIELDS)
        if include_salary:
            data["salary_cents"] = employee.salary_cents
            data["currency"] = employee.currency
        return EmployeeRead.model_validate(data)

    def _audit_snapshot(self, employee: Employee, actor: User) -> dict[str, object]:
        data = snapshot(employee, _PUBLIC_FIELDS)
        if role_allows(actor.role, Permission.EMPLOYEES_COMPENSATION):
            data["salary_cents"] = employee.salary_cents
            data["currency"] = employee.currency
        elif employee.salary_cents is not None:
            data["salary_cents"] = "hidden"
        return data
