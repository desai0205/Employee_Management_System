"""HTTP dependencies.

Routes receive services from here and do not query the database.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.core.rbac import Permission, ensure_permission
from app.core.security import decode_access_token
from app.db.session import current_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.attendance import AttendanceService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.container import (
    build_attendance_service,
    build_audit_service,
    build_auth_service,
    build_dashboard_service,
    build_department_service,
    build_employee_service,
    build_health_service,
    build_leave_service,
    build_report_service,
)
from app.services.dashboard import DashboardService
from app.services.department import DepartmentService
from app.services.employee import EmployeeService
from app.services.health import HealthService
from app.services.leave import LeaveService
from app.services.report import ReportService

_bearer = HTTPBearer(auto_error=False)
logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Caller:
    ip_address: str | None
    user_agent: str | None


def get_db_session() -> AsyncSession:
    return current_session()


def get_app_settings() -> Settings:
    return get_settings()


def get_caller(request: Request) -> Caller:
    client = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    if user_agent and len(user_agent) > 255:
        user_agent = user_agent[:255]
    return Caller(ip_address=client, user_agent=user_agent)


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[str | None, Query(max_length=64)] = None,
    order: Annotated[Literal["asc", "desc"], Query()] = "asc",
) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort=sort, order=order)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()
    claims = decode_access_token(credentials.credentials, settings.secret_key)
    user = await UserRepository(session).get(claims.user_id)
    if user is None or not user.is_active or claims.role != user.role.value:
        raise UnauthorizedError("invalid_token", "Access token is invalid.")
    logger.debug("authenticated", user_id=str(user.id))
    return user


def require(permission: Permission) -> Callable[..., object]:
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        ensure_permission(user.role, permission)
        return user

    return checker


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    return build_auth_service(session)


def get_employee_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmployeeService:
    return build_employee_service(session)


def get_department_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DepartmentService:
    return build_department_service(session)


def get_attendance_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttendanceService:
    return build_attendance_service(session)


def get_leave_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LeaveService:
    return build_leave_service(session)


def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardService:
    return build_dashboard_service(session)


def get_report_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportService:
    return build_report_service(session)


def get_audit_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditService:
    return build_audit_service(session)


def get_health_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthService:
    return build_health_service(session)
