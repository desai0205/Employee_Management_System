"""Report export persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReportExportStatus
from app.models.report_export import ReportExport
from app.repositories.base import Repository


class ReportExportRepository(Repository[ReportExport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReportExport)

    async def get_for_update(self, export_id: uuid.UUID) -> ReportExport | None:
        statement = (
            select(ReportExport).where(ReportExport.id == export_id).with_for_update()
        )
        result = await self.session.scalars(statement)
        return result.one_or_none()

    async def list_pending_ids(self, limit: int = 20) -> list[uuid.UUID]:
        statement = (
            select(ReportExport.id)
            .where(ReportExport.status == ReportExportStatus.PENDING)
            .order_by(ReportExport.created_at)
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())
