"""Leave type, balance, and request schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.models.enums import LeaveStatus
from app.schemas.common import ORMModel


class LeaveTypeCreate(ORMModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=2, max_length=32)
    default_annual_days: Decimal = Field(gt=0, le=Decimal("366.0"))
    is_paid: bool = True


class LeaveTypeRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    default_annual_days: Decimal
    is_paid: bool
    is_active: bool


class LeaveBalanceCreate(ORMModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    allocated_days: Decimal | None = Field(default=None, ge=0, le=Decimal("366.0"))


class LeaveBalanceRead(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    allocated_days: Decimal
    used_days: Decimal


class LeaveRequestCreate(ORMModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=2000)


class LeaveDecision(ORMModel):
    note: str | None = Field(default=None, max_length=2000)


class LeaveRequestRead(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days: Decimal
    reason: str
    status: LeaveStatus
    approver_id: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
