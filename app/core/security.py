"""Password hashing and JWT access tokens."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.exceptions import UnauthorizedError

_HASHER = PasswordHash.recommended()
_ALGORITHM = "HS256"


def validate_password_policy(password: str) -> str:
    has_letter = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)
    if len(password) < 8 or not has_letter or not has_digit:
        raise ValueError(
            "Password must be at least 8 characters and include a letter and a number."
        )
    return password


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _HASHER.verify(password, password_hash)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    role: str
    jti: str


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    secret: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=expires_minutes),
    }
    token: str = jwt.encode(payload, secret, algorithm=_ALGORITHM)
    return token


def decode_access_token(token: str, secret: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
        user_id = uuid.UUID(str(payload["sub"]))
        role = str(payload["role"])
        jti = str(payload["jti"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise UnauthorizedError("invalid_token", "Access token is invalid.") from exc
    return AccessTokenClaims(user_id=user_id, role=role, jti=jti)
