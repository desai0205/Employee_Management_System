"""Translate database constraint names into API conflicts."""

from typing import NoReturn

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError

_CONSTRAINT_MESSAGES: dict[str, tuple[str, str]] = {
    "uq_users_email": ("duplicate_email", "Email is already in use."),
    "uq_employees_email": ("duplicate_email", "Email is already in use."),
    "uq_employees_employee_code": (
        "duplicate_employee_code",
        "Employee code is already in use.",
    ),
    "uq_employees_user_id": (
        "duplicate_user_link",
        "That account is already linked to an employee.",
    ),
    "uq_departments_name": (
        "duplicate_department",
        "Department name is already in use.",
    ),
    "uq_departments_code": (
        "duplicate_department",
        "Department code is already in use.",
    ),
    "uq_leave_types_name": (
        "duplicate_leave_type",
        "Leave type name is already in use.",
    ),
    "uq_leave_types_code": (
        "duplicate_leave_type",
        "Leave type code is already in use.",
    ),
    "uq_attendance_employee_date": (
        "attendance_exists",
        "Attendance already exists for that day.",
    ),
    "uq_leave_balances_employee_type_year": (
        "duplicate_leave_balance",
        "A balance already exists for that employee, type, and year.",
    ),
    "ex_leave_requests_no_overlap": (
        "leave_overlap",
        "Leave overlaps an existing request.",
    ),
    "uq_refresh_tokens_token_hash": (
        "duplicate_token",
        "Refresh token already exists.",
    ),
}


def raise_for_integrity(exc: IntegrityError) -> NoReturn:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if isinstance(constraint, str) and constraint in _CONSTRAINT_MESSAGES:
        code, message = _CONSTRAINT_MESSAGES[constraint]
        raise ConflictError(code, message) from exc
    text = str(exc.orig).lower()
    for name, (code, message) in _CONSTRAINT_MESSAGES.items():
        if name in text:
            raise ConflictError(code, message) from exc
    raise ConflictError(
        "conflict", "The request conflicts with existing data."
    ) from exc
