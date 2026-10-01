"""Shared and domain enums persisted as PostgreSQL enum types."""

import enum

from sqlalchemy import Enum


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    HR = "hr"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class EmploymentStatus(enum.StrEnum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class AttendanceStatus(enum.StrEnum):
    PRESENT = "present"
    LATE = "late"
    HALF_DAY = "half_day"
    ABSENT = "absent"
    ON_LEAVE = "on_leave"


class AttendanceSource(enum.StrEnum):
    SELF_SERVICE = "self_service"
    CORRECTION = "correction"


class LeaveStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReportType(enum.StrEnum):
    HEADCOUNT = "headcount"
    ATTENDANCE = "attendance"
    LEAVE = "leave"


class ReportExportStatus(enum.StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
