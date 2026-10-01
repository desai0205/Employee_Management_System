"""Employee profile, reporting line, and optional login account."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EmploymentStatus, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.user import User


class Employee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "manager_id IS NULL OR manager_id <> id", name="manager_not_self"
        ),
        CheckConstraint(
            "salary_cents IS NULL OR salary_cents >= 0", name="salary_nonnegative"
        ),
        CheckConstraint(
            "employment_status <> 'terminated' OR termination_date IS NOT NULL",
            name="termination_date_required",
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    employee_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    job_title: Mapped[str] = mapped_column(String(120), nullable=False)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        pg_enum(EmploymentStatus, "employment_status"),
        nullable=False,
        default=EmploymentStatus.ACTIVE,
        index=True,
    )
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    salary_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    user: Mapped["User | None"] = relationship(back_populates="employee", lazy="raise")
    department: Mapped["Department"] = relationship(
        back_populates="employees",
        foreign_keys=[department_id],
        lazy="raise",
    )
    manager: Mapped["Employee | None"] = relationship(
        remote_side="Employee.id",
        foreign_keys=[manager_id],
        back_populates="direct_reports",
        lazy="raise",
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        back_populates="manager",
        foreign_keys=[manager_id],
        lazy="raise",
    )
