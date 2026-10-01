"""Report and export schemas."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ReportExportStatus, ReportType
from app.schemas.common import ORMModel


class ReportWindow(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    department_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ReportWindow":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from.")
        return self


class DepartmentCount(BaseModel):
    department_id: uuid.UUID
    department_name: str
    count: int


class HeadcountReport(BaseModel):
    total: int
    by_status: dict[str, int]
    by_department: list[DepartmentCount]


class AttendanceReport(BaseModel):
    date_from: date
    date_to: date
    by_status: dict[str, int]


class LeaveReport(BaseModel):
    date_from: date
    date_to: date
    by_status: dict[str, int]


class ReportExportCreate(ReportWindow):
    report_type: ReportType


class ReportExportRead(ORMModel):
    id: uuid.UUID
    report_type: ReportType
    status: ReportExportStatus
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime


class ReportFilter(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    department_id: uuid.UUID | None = Field(default=None)
