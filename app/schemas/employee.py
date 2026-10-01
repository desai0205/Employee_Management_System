"""Employee schemas. Compensation fields stay unset when the viewer cannot see them."""

import uuid
from datetime import date

from pydantic import EmailStr, Field, field_validator

from app.core.security import validate_password_policy
from app.models.enums import EmploymentStatus, UserRole
from app.schemas.common import ORMModel


class EmployeeCreate(ORMModel):
    employee_code: str = Field(min_length=2, max_length=32)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    department_id: uuid.UUID
    manager_id: uuid.UUID | None = None
    job_title: str = Field(min_length=1, max_length=120)
    hire_date: date
    salary_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    account_password: str | None = Field(default=None, max_length=128)
    account_role: UserRole = UserRole.EMPLOYEE

    @field_validator("employee_code")
    @classmethod
    def code_is_compact(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned.replace("-", "").isalnum():
            raise ValueError("Employee code must be alphanumeric.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("account_password")
    @classmethod
    def password_policy(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_password_policy(value)


class EmployeeUpdate(ORMModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    job_title: str | None = Field(default=None, min_length=1, max_length=120)
    hire_date: date | None = None
    salary_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class EmployeeTerminate(ORMModel):
    termination_date: date


class EmployeeRead(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    employee_code: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    department_id: uuid.UUID
    manager_id: uuid.UUID | None
    job_title: str
    employment_status: EmploymentStatus
    hire_date: date
    termination_date: date | None
    salary_cents: int | None = None
    currency: str | None = None
