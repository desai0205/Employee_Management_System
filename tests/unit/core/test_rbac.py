"""Permission map."""

import pytest

from app.core.exceptions import ForbiddenError
from app.core.rbac import Permission, ensure_permission, role_allows
from app.models.enums import UserRole


def test_admin_can_read_audit_and_hr_cannot() -> None:
    assert role_allows(UserRole.ADMIN, Permission.AUDIT_READ)
    assert not role_allows(UserRole.HR, Permission.AUDIT_READ)


def test_manager_can_approve_leave_but_cannot_correct_attendance() -> None:
    assert role_allows(UserRole.MANAGER, Permission.LEAVE_APPROVE)
    assert not role_allows(UserRole.MANAGER, Permission.ATTENDANCE_CORRECT)
    assert not role_allows(UserRole.MANAGER, Permission.EMPLOYEES_COMPENSATION)


def test_employee_cannot_write_employees() -> None:
    assert role_allows(UserRole.EMPLOYEE, Permission.LEAVE_REQUEST)
    with pytest.raises(ForbiddenError):
        ensure_permission(UserRole.EMPLOYEE, Permission.EMPLOYEES_WRITE)
