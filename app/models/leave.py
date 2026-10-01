"""Leave types, yearly balances, and requests."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeaveStatus, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.employee import Employee


class LeaveType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_types"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    default_annual_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    is_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class LeaveBalance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        CheckConstraint(
            "allocated_days >= 0 AND used_days >= 0 AND used_days <= allocated_days",
            name="days_within_allocation",
        ),
        Index(
            "uq_leave_balances_employee_type_year",
            "employee_id",
            "leave_type_id",
            "year",
            unique=True,
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(nullable=False)
    allocated_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), nullable=False, default=Decimal("0.0")
    )

    employee: Mapped["Employee"] = relationship(lazy="raise")
    leave_type: Mapped[LeaveType] = relationship(lazy="raise")


class LeaveRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="end_on_or_after_start"),
        Index("ix_leave_requests_employee_status", "employee_id", "status"),
        Index("ix_leave_requests_status_start", "status", "start_date"),
        ExcludeConstraint(
            ("employee_id", "="),
            (text("daterange(start_date, end_date, '[]')"), "&&"),
            where=text("status IN ('pending', 'approved')"),
            name="ex_leave_requests_no_overlap",
            using="gist",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        pg_enum(LeaveStatus, "leave_status"),
        nullable=False,
        default=LeaveStatus.PENDING,
        index=True,
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    employee: Mapped["Employee"] = relationship(
        foreign_keys=[employee_id], lazy="raise"
    )
    leave_type: Mapped[LeaveType] = relationship(lazy="raise")
    approver: Mapped["Employee | None"] = relationship(
        foreign_keys=[approver_id], lazy="raise"
    )
