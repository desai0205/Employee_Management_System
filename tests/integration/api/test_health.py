"""Health endpoints."""

from httpx import AsyncClient


async def test_liveness_and_readiness(client: AsyncClient) -> None:
    live = await client.get("/api/v1/health/live")
    ready = await client.get("/api/v1/health/ready")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"
    assert ready.json()["redis"] == "ok"
    assert live.headers["x-request-id"]
