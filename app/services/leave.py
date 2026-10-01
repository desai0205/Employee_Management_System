"""Leave requests, balances, and approval rules."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import PageParams
from app.core.post_commit import schedule_job
from app.core.rbac import Permission, ensure_permission, role_allows
from app.core.time import utc_now
from app.models.enums import EmploymentStatus, LeaveStatus, UserRole
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.models.user import User
from app.repositories.employee import EmployeeRepository
from app.repositories.errors import raise_for_integrity
from app.repositories.leave import LeaveRepository
from app.schemas.common import Page
from app.schemas.leave import (
    LeaveBalanceCreate,
    LeaveBalanceRead,
    LeaveDecision,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveTypeCreate,
    LeaveTypeRead,
)
from app.services.audit import AuditService, snapshot
from app.services.scope import ScopeService

_MAX_SPAN_DAYS = 366


def count_weekdays(start: date, end: date) -> Decimal:
    if end < start:
        raise ConflictError(
            "invalid_leave_dates", "End date must be on or after the start date."
        )
    if (end - start).days > _MAX_SPAN_DAYS:
        raise ConflictError(
            "invalid_leave_dates", "Leave requests cannot span more than a year."
        )
    if start.year != end.year:
        raise ConflictError(
            "invalid_leave_dates", "Leave requests cannot cross a calendar year."
        )
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    if days == 0:
        raise ConflictError(
            "leave_no_working_days", "The selected range has no working days."
        )
    return Decimal(days)


class LeaveService:
    def __init__(
        self,
        leaves: LeaveRepository,
        employees: EmployeeRepository,
        scope: ScopeService,
        audit: AuditService,
    ) -> None:
        self.leaves = leaves
        self.employees = employees
        self.scope = scope
        self.audit = audit

    async def list_types(self, *, active_only: bool) -> list[LeaveTypeRead]:
        rows = await self.leaves.list_types(active_only=active_only)
        return [LeaveTypeRead.model_validate(row) for row in rows]

    async def create_type(
        self, actor: User, payload: LeaveTypeCreate, *, ip_address: str | None
    ) -> LeaveTypeRead:
        ensure_permission(actor.role, Permission.LEAVE_MANAGE)
        leave_type = LeaveType(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            code=payload.code.strip().upper(),
            default_annual_days=payload.default_annual_days,
            is_paid=payload.is_paid,
            is_active=True,
        )
        try:
            await self.leaves.add_type(leave_type)
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="leave_type.created",
            entity_type="leave_type",
            entity_id=leave_type.id,
            after=snapshot(
                leave_type, ["id", "name", "code", "default_annual_days", "is_paid"]
            ),
            ip_address=ip_address,
        )
        return LeaveTypeRead.model_validate(leave_type)

    async def list_balances(
        self,
        actor: User,
        *,
        employee_id: uuid.UUID | None,
        year: int | None,
    ) -> list[LeaveBalanceRead]:
        visible = await self.scope.visible_employee_ids(actor)
        if employee_id is not None and not ScopeService.contains(visible, employee_id):
            raise ForbiddenError("You can only view leave balances in your scope.")
        rows = await self.leaves.list_balances(
            visible, employee_id=employee_id, year=year
        )
        return [LeaveBalanceRead.model_validate(row) for row in rows]

    async def allocate(
        self, actor: User, payload: LeaveBalanceCreate, *, ip_address: str | None
    ) -> LeaveBalanceRead:
        ensure_permission(actor.role, Permission.LEAVE_MANAGE)
        employee = await self.employees.get(payload.employee_id)
        if employee is None:
            raise NotFoundError("employee_not_found", "Employee was not found.")
        leave_type = await self.leaves.get_type(payload.leave_type_id)
        if leave_type is None or not leave_type.is_active:
            raise NotFoundError("leave_type_not_found", "Leave type was not found.")
        allocated = (
            payload.allocated_days
            if payload.allocated_days is not None
            else leave_type.default_annual_days
        )
        balance = LeaveBalance(
            id=uuid.uuid4(),
            employee_id=payload.employee_id,
            leave_type_id=payload.leave_type_id,
            year=payload.year,
            allocated_days=allocated,
            used_days=Decimal("0.0"),
        )
        try:
            await self.leaves.add_balance(balance)
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="leave_balance.allocated",
            entity_type="leave_balance",
            entity_id=balance.id,
            after=snapshot(
                balance,
                [
                    "id",
                    "employee_id",
                    "leave_type_id",
                    "year",
                    "allocated_days",
                    "used_days",
                ],
            ),
            ip_address=ip_address,
        )
        return LeaveBalanceRead.model_validate(balance)

    async def request_leave(
        self, actor: User, payload: LeaveRequestCreate, *, ip_address: str | None
    ) -> LeaveRequestRead:
        profile = await self.employees.get_by_user_id(actor.id)
        if profile is None:
            raise ConflictError(
                "employee_profile_required",
                "An employee profile is required to request leave.",
            )
        if profile.employment_status == EmploymentStatus.TERMINATED:
            raise ConflictError(
                "employee_terminated", "Terminated employees cannot request leave."
            )
        days = count_weekdays(payload.start_date, payload.end_date)
        leave_type = await self.leaves.get_type(payload.leave_type_id)
        if leave_type is None or not leave_type.is_active:
            raise NotFoundError("leave_type_not_found", "Leave type was not found.")
        if await self.leaves.has_overlap(
            profile.id, payload.start_date, payload.end_date
        ):
            raise ConflictError("leave_overlap", "Leave overlaps an existing request.")
        balance = await self.leaves.get_balance_for_update(
            profile.id, payload.leave_type_id, payload.start_date.year
        )
        if balance is None:
            raise ConflictError(
                "leave_balance_missing", "No leave balance is allocated for that year."
            )
        pending = await self.leaves.sum_pending_days(
            profile.id, payload.leave_type_id, payload.start_date.year
        )
        remaining = balance.allocated_days - balance.used_days - pending
        if days > remaining:
            raise ConflictError(
                "leave_balance_exceeded", "Requested days exceed the remaining balance."
            )
        request = LeaveRequest(
            id=uuid.uuid4(),
            employee_id=profile.id,
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            days=days,
            reason=payload.reason.strip(),
            status=LeaveStatus.PENDING,
        )
        self.leaves.add(request)
        try:
            await self.leaves.flush()
        except IntegrityError as exc:
            raise_for_integrity(exc)
        await self.audit.record(
            actor_user_id=actor.id,
            action="leave.requested",
            entity_type="leave_request",
            entity_id=request.id,
            after=snapshot(
                request,
                ["id", "employee_id", "start_date", "end_date", "days", "status"],
            ),
            ip_address=ip_address,
        )
        return LeaveRequestRead.model_validate(request)

    async def list_requests(
        self,
        actor: User,
        params: PageParams,
        *,
        employee_id: uuid.UUID | None,
        status: LeaveStatus | None,
        leave_type_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> Page[LeaveRequestRead]:
        visible = await self.scope.visible_employee_ids(actor)
        if employee_id is not None and not ScopeService.contains(visible, employee_id):
            raise ForbiddenError("You can only view leave in your scope.")
        rows, total, pages = await self.leaves.list_page(
            params,
            visible_ids=visible,
            employee_id=employee_id,
            status=status,
            leave_type_id=leave_type_id,
            date_from=date_from,
            date_to=date_to,
        )
        return Page(
            items=[LeaveRequestRead.model_validate(row) for row in rows],
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=pages,
        )

    async def get_request(self, actor: User, request_id: uuid.UUID) -> LeaveRequestRead:
        request = await self._get_visible(actor, request_id)
        return LeaveRequestRead.model_validate(request)

    async def approve(
        self,
        actor: User,
        request_id: uuid.UUID,
        payload: LeaveDecision,
        *,
        ip_address: str | None,
    ) -> LeaveRequestRead:
        request = await self._get_request(request_id)
        await self._ensure_can_decide(actor, request)
        if request.status != LeaveStatus.PENDING:
            raise ConflictError(
                "leave_not_pending", "Only pending leave can be approved."
            )
        balance = await self.leaves.get_balance_for_update(
            request.employee_id, request.leave_type_id, request.start_date.year
        )
        if balance is None:
            raise ConflictError(
                "leave_balance_missing", "No leave balance is allocated for that year."
            )
        if balance.used_days + request.days > balance.allocated_days:
            raise ConflictError(
                "leave_balance_exceeded", "Requested days exceed the remaining balance."
            )
        balance.used_days = balance.used_days + request.days
        await self._decide(
            actor,
            request,
            LeaveStatus.APPROVED,
            payload.note,
            action="leave.approved",
            ip_address=ip_address,
        )
        schedule_job("notify_leave_decision", str(request.id))
        return LeaveRequestRead.model_validate(request)

    async def reject(
        self,
        actor: User,
        request_id: uuid.UUID,
        payload: LeaveDecision,
        *,
        ip_address: str | None,
    ) -> LeaveRequestRead:
        request = await self._get_request(request_id)
        await self._ensure_can_decide(actor, request)
        if request.status != LeaveStatus.PENDING:
            raise ConflictError(
                "leave_not_pending", "Only pending leave can be rejected."
            )
        await self._decide(
            actor,
            request,
            LeaveStatus.REJECTED,
            payload.note,
            action="leave.rejected",
            ip_address=ip_address,
        )
        schedule_job("notify_leave_decision", str(request.id))
        return LeaveRequestRead.model_validate(request)

    async def cancel(
        self, actor: User, request_id: uuid.UUID, *, ip_address: str | None
    ) -> LeaveRequestRead:
        request = await self._get_request(request_id)
        owner = await self._is_owner(actor, request)
        can_cancel = (request.status == LeaveStatus.PENDING and owner) or role_allows(
            actor.role, Permission.LEAVE_MANAGE
        )
        if not can_cancel:
            raise ForbiddenError("You cannot cancel this leave request.")
        if request.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
            raise ConflictError(
                "leave_not_cancellable",
                "This leave request can no longer be cancelled.",
            )
        if request.status == LeaveStatus.APPROVED:
            balance = await self.leaves.get_balance_for_update(
                request.employee_id,
                request.leave_type_id,
                request.start_date.year,
            )
            if balance is not None:
                restored = balance.used_days - request.days
                balance.used_days = restored if restored > 0 else Decimal("0.0")
        await self._decide(
            actor,
            request,
            LeaveStatus.CANCELLED,
            None,
            action="leave.cancelled",
            ip_address=ip_address,
        )
        schedule_job("notify_leave_decision", str(request.id))
        return LeaveRequestRead.model_validate(request)

    async def record_notification(self, request_id: uuid.UUID) -> None:
        request = await self.leaves.get(request_id)
        if request is None:
            raise NotFoundError(
                "leave_request_not_found", "Leave request was not found."
            )
        status = request.status.value
        if await self.audit.repository.exists_notification(str(request.id), status):
            return
        await self.audit.record(
            actor_user_id=None,
            action="notification.leave_decision",
            entity_type="leave_request",
            entity_id=request.id,
            after={"status": status, "employee_id": str(request.employee_id)},
        )

    async def _decide(
        self,
        actor: User,
        request: LeaveRequest,
        status: LeaveStatus,
        note: str | None,
        *,
        action: str,
        ip_address: str | None,
    ) -> None:
        before = snapshot(request, ["id", "status", "approver_id"])
        approver = await self.employees.get_by_user_id(actor.id)
        request.status = status
        request.approver_id = approver.id if approver else None
        request.decided_at = utc_now()
        request.decision_note = note
        await self.leaves.flush()
        await self.audit.record(
            actor_user_id=actor.id,
            action=action,
            entity_type="leave_request",
            entity_id=request.id,
            before=before,
            after=snapshot(request, ["id", "status", "approver_id", "decision_note"]),
            ip_address=ip_address,
        )

    async def _ensure_can_decide(self, actor: User, request: LeaveRequest) -> None:
        ensure_permission(actor.role, Permission.LEAVE_APPROVE)
        requester = await self.employees.get(request.employee_id)
        if requester is None:
            raise NotFoundError("employee_not_found", "Employee was not found.")
        if requester.user_id == actor.id:
            raise ForbiddenError("You cannot decide your own leave request.")
        if actor.role in (UserRole.ADMIN, UserRole.HR):
            return
        approver = await self.employees.get_by_user_id(actor.id)
        if approver is None or requester.manager_id != approver.id:
            raise ForbiddenError("You can only decide leave for your direct reports.")

    async def _is_owner(self, actor: User, request: LeaveRequest) -> bool:
        profile = await self.employees.get_by_user_id(actor.id)
        return profile is not None and profile.id == request.employee_id

    async def _get_request(self, request_id: uuid.UUID) -> LeaveRequest:
        request = await self.leaves.get(request_id)
        if request is None:
            raise NotFoundError(
                "leave_request_not_found", "Leave request was not found."
            )
        return request

    async def _get_visible(self, actor: User, request_id: uuid.UUID) -> LeaveRequest:
        request = await self._get_request(request_id)
        visible = await self.scope.visible_employee_ids(actor)
        if not ScopeService.contains(visible, request.employee_id):
            raise ForbiddenError("You can only view leave in your scope.")
        return request
