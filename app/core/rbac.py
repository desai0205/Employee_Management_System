"""Role permission map. Routes and services both call this module."""

from enum import StrEnum

from app.core.exceptions import ForbiddenError
from app.models.enums import UserRole


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    EMPLOYEES_READ = "employees:read"
    EMPLOYEES_WRITE = "employees:write"
    EMPLOYEES_TERMINATE = "employees:terminate"
    EMPLOYEES_COMPENSATION = "employees:compensation"
    DEPARTMENTS_READ = "departments:read"
    DEPARTMENTS_WRITE = "departments:write"
    ATTENDANCE_SELF = "attendance:self"
    ATTENDANCE_READ = "attendance:read"
    ATTENDANCE_CORRECT = "attendance:correct"
    LEAVE_REQUEST = "leave:request"
    LEAVE_APPROVE = "leave:approve"
    LEAVE_MANAGE = "leave:manage"
    REPORTS_READ = "reports:read"
    AUDIT_READ = "audit:read"


_ALL = frozenset(Permission)

_HR = frozenset(
    permission for permission in Permission if permission is not Permission.AUDIT_READ
)

_MANAGER = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.EMPLOYEES_READ,
        Permission.DEPARTMENTS_READ,
        Permission.ATTENDANCE_SELF,
        Permission.ATTENDANCE_READ,
        Permission.LEAVE_REQUEST,
        Permission.LEAVE_APPROVE,
        Permission.REPORTS_READ,
    }
)

_EMPLOYEE = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.EMPLOYEES_READ,
        Permission.DEPARTMENTS_READ,
        Permission.ATTENDANCE_SELF,
        Permission.ATTENDANCE_READ,
        Permission.LEAVE_REQUEST,
        Permission.REPORTS_READ,
    }
)

_ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.ADMIN: _ALL,
    UserRole.HR: _HR,
    UserRole.MANAGER: _MANAGER,
    UserRole.EMPLOYEE: _EMPLOYEE,
}


def role_allows(role: UserRole, permission: Permission) -> bool:
    return permission in _ROLE_PERMISSIONS[role]


def ensure_permission(role: UserRole, permission: Permission) -> None:
    if not role_allows(role, permission):
        raise ForbiddenError
