"""Query helpers shared by repositories. Sort fields are never interpolated into SQL."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import AppError
from app.core.pagination import PageParams, page_count
from app.db.base import Base


class Repository[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    async def get(self, entity_id: Any) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def flush(self) -> None:
        await self.session.flush()


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def sort_column(
    sort: str | None,
    order: str,
    allowed: dict[str, InstrumentedAttribute[Any]],
    default: str,
) -> Any:
    key = sort or default
    column = allowed.get(key)
    if column is None:
        raise AppError(
            "invalid_sort", f"Sort field '{key}' is not allowed.", status_code=422
        )
    if order == "desc":
        return column.desc()
    return column.asc()


async def paginate(
    session: AsyncSession,
    statement: Select[Any],
    params: PageParams,
    ordering: Any,
) -> tuple[list[Any], int, int]:
    count_source = statement.order_by(None).subquery()
    total = int(
        await session.scalar(select(func.count()).select_from(count_source)) or 0
    )
    result = await session.scalars(
        statement.order_by(ordering).offset(params.offset).limit(params.page_size)
    )
    return list(result.all()), total, page_count(total, params.page_size)
