"""Password hashing and access-token claims."""

import uuid

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-key-32-characters"


def test_password_hash_verifies_and_rejects_wrong_password() -> None:
    stored = hash_password("Password1")
    assert verify_password("Password1", stored)
    assert not verify_password("Password2", stored)


def test_access_token_carries_subject_and_role() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        role="manager",
        secret=SECRET,
        expires_minutes=15,
    )
    claims = decode_access_token(token, SECRET)
    assert claims.user_id == user_id
    assert claims.role == "manager"
    assert claims.jti


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        role="employee",
        secret=SECRET,
        expires_minutes=15,
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(token + "x", SECRET)
