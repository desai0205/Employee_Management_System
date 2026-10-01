"""User queries."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.scalars(
            select(User).where(User.email == email.lower())
        )
        return result.one_or_none()

    async def get(self, entity_id: uuid.UUID) -> User | None:
        return await self.session.get(User, entity_id)

    async def count(self) -> int:
        return int(
            await self.session.scalar(select(func.count()).select_from(User)) or 0
        )
