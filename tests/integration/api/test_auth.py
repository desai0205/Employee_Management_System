"""Login and refresh-token rotation over HTTP."""

from httpx import AsyncClient

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.enums import UserRole
from app.models.user import User


async def test_login_and_refresh_rotation(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            User(
                email="admin@example.com",
                password_hash=hash_password("Password1"),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password1"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    rotated = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert rotated.status_code == 200
    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_token_reused"
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
    )
    assert me.status_code == 200
