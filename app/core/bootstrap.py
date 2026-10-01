"""Creates the first administrator when bootstrap credentials are configured."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_policy
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository

logger = get_logger(__name__)


async def bootstrap_admin(session: AsyncSession) -> None:
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password
    if not email or not password:
        return
    validate_password_policy(password)
    users = UserRepository(session)
    if await users.get_by_email(email) is not None:
        return
    users.add(
        User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await users.flush()
    logger.info("bootstrap_admin_created", email=email)
