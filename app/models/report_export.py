"""Async report export tracked until the worker finishes it."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ReportExportStatus, ReportType, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReportExport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_exports"

    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    report_type: Mapped[ReportType] = mapped_column(
        pg_enum(ReportType, "report_type"), nullable=False
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[ReportExportStatus] = mapped_column(
        pg_enum(ReportExportStatus, "report_export_status"),
        nullable=False,
        default=ReportExportStatus.PENDING,
        index=True,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
