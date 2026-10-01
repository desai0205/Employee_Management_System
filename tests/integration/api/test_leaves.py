"""Leave approval changes the balance inside the request transaction."""

from httpx import AsyncClient

from app.db.session import get_session_factory
from app.models.enums import UserRole
from tests.factories import make_department, make_employee, make_user


async def test_manager_approval_consumes_balance(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await make_user(session, "admin@example.com", UserRole.ADMIN)
        manager_user = await make_user(session, "manager@example.com", UserRole.MANAGER)
        staff_user = await make_user(session, "staff@example.com", UserRole.EMPLOYEE)
        department = await make_department(session, "OPS")
        manager = await make_employee(
            session,
            department,
            code="MGR",
            email="manager@example.com",
            user=manager_user,
        )
        await make_employee(
            session,
            department,
            code="STAFF",
            email="staff@example.com",
            user=staff_user,
            manager_id=manager.id,
        )
        await session.commit()

    admin = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Password1"},
        )
    ).json()
    manager_token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "manager@example.com", "password": "Password1"},
        )
    ).json()
    staff = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "staff@example.com", "password": "Password1"},
        )
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    staff_headers = {"Authorization": f"Bearer {staff['access_token']}"}
    manager_headers = {"Authorization": f"Bearer {manager_token['access_token']}"}

    leave_type = await client.post(
        "/api/v1/leave-types",
        headers=admin_headers,
        json={
            "name": "Annual",
            "code": "ANN",
            "default_annual_days": "2.0",
            "is_paid": True,
        },
    )
    assert leave_type.status_code == 201
    type_id = leave_type.json()["id"]
    employees = await client.get(
        "/api/v1/employees",
        params={"q": "STAFF"},
        headers=admin_headers,
    )
    staff_id = employees.json()["items"][0]["id"]
    balance = await client.post(
        "/api/v1/leave-balances",
        headers=admin_headers,
        json={
            "employee_id": staff_id,
            "leave_type_id": type_id,
            "year": 2026,
            "allocated_days": "2.0",
        },
    )
    assert balance.status_code == 201

    requested = await client.post(
        "/api/v1/leaves",
        headers=staff_headers,
        json={
            "leave_type_id": type_id,
            "start_date": "2026-01-05",
            "end_date": "2026-01-06",
            "reason": "Clinic",
        },
    )
    assert requested.status_code == 201
    leave_id = requested.json()["id"]
    approved = await client.post(
        f"/api/v1/leaves/{leave_id}/approve",
        headers=manager_headers,
        json={"note": "Approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    balances = await client.get("/api/v1/leave-balances", headers=staff_headers)
    assert balances.status_code == 200
    assert float(balances.json()[0]["used_days"]) == 2.0
