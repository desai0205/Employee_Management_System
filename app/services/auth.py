"""Login, refresh-token rotation, logout, and password changes."""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.config import Settings
from app.core.exceptions import AppError, UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import utc_now
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.employee import EmployeeRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import MeResponse, TokenResponse
from app.services.audit import AuditService


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        tokens: RefreshTokenRepository,
        employees: EmployeeRepository,
        audit: AuditService,
        rate_limiter: RateLimiter,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.users = users
        self.tokens = tokens
        self.employees = employees
        self.audit = audit
        self.rate_limiter = rate_limiter
        self.settings = settings
        self._clock = clock or utc_now

    async def login(
        self,
        email: str,
        password: str,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        normalized = email.lower()
        await self.rate_limiter.hit(normalized, ip_address)
        user = await self.users.get_by_email(normalized)
        if (
            user is None
            or not user.is_active
            or not verify_password(password, user.password_hash)
        ):
            raise UnauthorizedError("invalid_credentials", "Invalid email or password.")
        user.last_login_at = self._clock()
        response, _refresh_id = await self._issue_tokens(
            user,
            family_id=uuid.uuid4(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.audit.record(
            actor_user_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
        )
        return response

    async def refresh(
        self, raw_token: str, *, ip_address: str | None, user_agent: str | None
    ) -> TokenResponse:
        token = await self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is None:
            raise UnauthorizedError(
                "invalid_refresh_token", "Refresh token is invalid."
            )
        now = self._clock()
        if token.revoked_at is not None:
            await self.tokens.revoke_family(token.family_id, now)
            await self.audit.record(
                actor_user_id=token.user_id,
                action="auth.refresh_reuse",
                entity_type="user",
                entity_id=token.user_id,
                ip_address=ip_address,
            )
            raise UnauthorizedError(
                "refresh_token_reused", "Refresh token has been revoked."
            )
        if token.expires_at <= now:
            raise UnauthorizedError(
                "refresh_token_expired", "Refresh token has expired."
            )
        user = await self.users.get(token.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError(
                "invalid_refresh_token", "Refresh token is invalid."
            )
        token.revoked_at = now
        response, refresh_id = await self._issue_tokens(
            user,
            family_id=token.family_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        token.replaced_by_id = refresh_id
        await self.audit.record(
            actor_user_id=user.id,
            action="auth.refresh",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
        )
        return response

    async def logout(
        self, actor: User, raw_token: str, *, ip_address: str | None
    ) -> None:
        token = await self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is None or token.user_id != actor.id:
            raise UnauthorizedError(
                "invalid_refresh_token", "Refresh token is invalid."
            )
        if token.revoked_at is None:
            token.revoked_at = self._clock()
        await self.audit.record(
            actor_user_id=actor.id,
            action="auth.logout",
            entity_type="user",
            entity_id=actor.id,
            ip_address=ip_address,
        )

    async def change_password(
        self,
        actor: User,
        current_password: str,
        new_password: str,
        *,
        ip_address: str | None,
    ) -> None:
        if not verify_password(current_password, actor.password_hash):
            raise UnauthorizedError(
                "invalid_credentials", "Current password is incorrect."
            )
        if verify_password(new_password, actor.password_hash):
            raise AppError(
                "password_reused",
                "Choose a password that is different from the current one.",
                422,
            )
        actor.password_hash = hash_password(new_password)
        await self.tokens.revoke_all_for_user(actor.id, self._clock())
        await self.audit.record(
            actor_user_id=actor.id,
            action="auth.password_changed",
            entity_type="user",
            entity_id=actor.id,
            ip_address=ip_address,
        )

    async def me(self, actor: User) -> MeResponse:
        profile = await self.employees.get_by_user_id(actor.id)
        return MeResponse(
            id=actor.id,
            email=actor.email,
            role=actor.role,
            is_active=actor.is_active,
            employee_id=profile.id if profile else None,
        )

    async def _issue_tokens(
        self,
        user: User,
        *,
        family_id: uuid.UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[TokenResponse, uuid.UUID]:
        now = self._clock()
        raw_refresh = generate_refresh_token()
        refresh_id = uuid.uuid4()
        self.tokens.add(
            RefreshToken(
                id=refresh_id,
                user_id=user.id,
                token_hash=hash_refresh_token(raw_refresh),
                family_id=family_id,
                expires_at=now
                + timedelta(days=self.settings.refresh_token_expire_days),
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        await self.tokens.flush()
        access = create_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self.settings.secret_key,
            expires_minutes=self.settings.access_token_expire_minutes,
            now=now,
        )
        response = TokenResponse(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )
        return response, refresh_id
