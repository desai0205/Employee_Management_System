"""Attendance schemas."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.models.enums import AttendanceSource, AttendanceStatus
from app.schemas.common import ORMModel


class AttendanceRead(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    work_date: date
    check_in_at: datetime | None
    check_out_at: datetime | None
    status: AttendanceStatus
    source: AttendanceSource
    note: str | None


class AttendanceCorrection(ORMModel):
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=2000)
