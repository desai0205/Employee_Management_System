"""Liveness and readiness."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_health_service
from app.services.health import HealthService

router = APIRouter()


class HealthLive(BaseModel):
    status: str


class HealthReady(BaseModel):
    status: str
    database: str
    redis: str


@router.get("/health/live", response_model=HealthLive)
async def live() -> HealthLive:
    return HealthLive(status="ok")


@router.get("/health/ready", response_model=HealthReady)
async def ready(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> dict[str, str]:
    return await service.ready()
