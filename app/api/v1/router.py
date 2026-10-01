"""API version 1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    attendance,
    audit,
    auth,
    dashboard,
    departments,
    employees,
    health,
    leaves,
    reports,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(
    departments.router, prefix="/departments", tags=["departments"]
)
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(leaves.types_router, prefix="/leave-types", tags=["leave"])
api_router.include_router(
    leaves.balances_router, prefix="/leave-balances", tags=["leave"]
)
api_router.include_router(leaves.router, prefix="/leaves", tags=["leave"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
