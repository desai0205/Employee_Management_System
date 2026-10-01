"""Auth service rules with in-memory repositories."""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import AuthService

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


class Users:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, User] = {}

    def add(self, user: User) -> User:
        self.rows[user.id] = user
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return self.rows.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.rows.values() if user.email == email), None)

    async def flush(self) -> None:
        return None


class Tokens:
    def __init__(self) -> None:
        self.rows: list[RefreshToken] = []

    def add(self, token: RefreshToken) -> RefreshToken:
        self.rows.append(token)
        return token

    async def flush(self) -> None:
        return None

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return next((row for row in self.rows if row.token_hash == token_hash), None)

    async def revoke_family(self, family_id: uuid.UUID, revoked_at: datetime) -> None:
        for row in self.rows:
            if row.family_id == family_id and row.revoked_at is None:
                row.revoked_at = revoked_at

    async def revoke_all_for_user(
        self, user_id: uuid.UUID, revoked_at: datetime
    ) -> None:
        for row in self.rows:
            if row.user_id == user_id and row.revoked_at is None:
                row.revoked_at = revoked_at


class Employees:
    async def get_by_user_id(self, _user_id: uuid.UUID) -> None:
        return None


class Audit:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def record(self, **kwargs: object) -> None:
        self.actions.append(str(kwargs["action"]))


class Limiter:
    async def hit(self, _email: str, _ip: str | None) -> None:
        return None


def settings() -> Settings:
    return Settings(
        app_env="local",
        secret_key="unit-test-secret-key-32-characters",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


def service() -> tuple[AuthService, Users, Tokens, Audit]:
    users = Users()
    tokens = Tokens()
    audit = Audit()
    user = User(
        id=uuid.uuid4(),
        email="ada@example.com",
        password_hash="",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    from app.core.security import hash_password

    user.password_hash = hash_password("Password1")
    users.add(user)
    auth = AuthService(
        users,  # type: ignore[arg-type]
        tokens,  # type: ignore[arg-type]
        Employees(),  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
        Limiter(),
        settings(),
        clock=lambda: NOW,
    )
    return auth, users, tokens, audit


@pytest.mark.asyncio
async def test_login_rejects_a_wrong_password() -> None:
    auth, _users, _tokens, audit = service()
    with pytest.raises(UnauthorizedError) as caught:
        await auth.login("ada@example.com", "nope", ip_address=None, user_agent=None)
    assert caught.value.code == "invalid_credentials"
    assert audit.actions == []


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_the_replacement_token() -> None:
    auth, _users, _tokens, _audit = service()
    first = await auth.login(
        "ada@example.com", "Password1", ip_address="127.0.0.1", user_agent="pytest"
    )
    rotated = await auth.refresh(
        first.refresh_token, ip_address="127.0.0.1", user_agent="pytest"
    )
    with pytest.raises(UnauthorizedError) as caught:
        await auth.refresh(
            first.refresh_token, ip_address="127.0.0.1", user_agent="pytest"
        )
    assert caught.value.code == "refresh_token_reused"
    with pytest.raises(UnauthorizedError):
        await auth.refresh(
            rotated.refresh_token, ip_address="127.0.0.1", user_agent="pytest"
        )


@pytest.mark.asyncio
async def test_password_change_revokes_refresh_tokens() -> None:
    auth, users, tokens, _audit = service()
    user = next(iter(users.rows.values()))
    issued = await auth.login(
        "ada@example.com", "Password1", ip_address=None, user_agent=None
    )
    await auth.change_password(user, "Password1", "Password2", ip_address=None)
    assert all(token.revoked_at is not None for token in tokens.rows)
    with pytest.raises(UnauthorizedError):
        await auth.refresh(issued.refresh_token, ip_address=None, user_agent=None)
