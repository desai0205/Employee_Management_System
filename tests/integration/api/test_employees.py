"""Employee list scope and pagination."""

from httpx import AsyncClient

from app.db.session import get_session_factory
from app.models.enums import UserRole
from tests.factories import make_department, make_employee, make_user


async def _seed_and_login(client: AsyncClient) -> tuple[str, str]:
    factory = get_session_factory()
    async with factory() as session:
        await make_user(session, "admin@example.com", UserRole.ADMIN)
        department = await make_department(session)
        employee_user = await make_user(session, "one@example.com", UserRole.EMPLOYEE)
        await make_employee(
            session,
            department,
            code="E1",
            email="one@example.com",
            user=employee_user,
        )
        await make_employee(session, department, code="E2", email="two@example.com")
        await make_employee(session, department, code="E3", email="three@example.com")
        await session.commit()

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password1"},
    )
    employee_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "one@example.com", "password": "Password1"},
    )
    assert admin_login.status_code == 200
    assert employee_login.status_code == 200
    return admin_login.json()["access_token"], employee_login.json()["access_token"]


async def test_pagination_and_cross_scope_read(client: AsyncClient) -> None:
    admin_token, employee_token = await _seed_and_login(client)
    listed = await client.get(
        "/api/v1/employees",
        params={"page_size": 2, "sort": "employee_code", "order": "asc"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2
    assert "salary_cents" in body["items"][0]

    own = await client.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert "salary_cents" not in own.json()["items"][0]
    other = next(
        item["id"] for item in body["items"] if item["email"] != "one@example.com"
    )
    forbidden = await client.get(
        f"/api/v1/employees/{other}",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
