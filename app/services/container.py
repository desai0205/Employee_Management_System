"""Composition helpers shared by HTTP dependencies and worker tasks."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import LoginRateLimiter, RateLimiter
from app.db.redis import get_redis_client
from app.repositories.attendance import AttendanceRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.department import DepartmentRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.leave import LeaveRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.report_export import ReportExportRepository
from app.repositories.user import UserRepository
from app.services.attendance import AttendanceService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.dashboard import DashboardService
from app.services.department import DepartmentService
from app.services.employee import EmployeeService
from app.services.health import HealthService
from app.services.leave import LeaveService
from app.services.report import ReportService
from app.services.scope import ScopeService


def build_audit_service(session: AsyncSession) -> AuditService:
    return AuditService(AuditLogRepository(session))


def build_auth_service(
    session: AsyncSession,
    settings: Settings | None = None,
    rate_limiter: RateLimiter | None = None,
) -> AuthService:
    current = settings or get_settings()
    limiter = rate_limiter
    if limiter is None:
        limiter = LoginRateLimiter(
            get_redis_client(),
            current.login_rate_limit,
            current.login_rate_window_seconds,
        )
    employees = EmployeeRepository(session)
    return AuthService(
        users=UserRepository(session),
        tokens=RefreshTokenRepository(session),
        employees=employees,
        audit=build_audit_service(session),
        rate_limiter=limiter,
        settings=current,
    )


def build_employee_service(
    session: AsyncSession, settings: Settings | None = None
) -> EmployeeService:
    employees = EmployeeRepository(session)
    return EmployeeService(
        employees=employees,
        users=UserRepository(session),
        departments=DepartmentRepository(session),
        scope=ScopeService(employees),
        audit=build_audit_service(session),
        settings=settings or get_settings(),
    )


def build_department_service(session: AsyncSession) -> DepartmentService:
    return DepartmentService(
        departments=DepartmentRepository(session),
        employees=EmployeeRepository(session),
        audit=build_audit_service(session),
    )


def build_attendance_service(
    session: AsyncSession, settings: Settings | None = None
) -> AttendanceService:
    employees = EmployeeRepository(session)
    return AttendanceService(
        attendance=AttendanceRepository(session),
        employees=employees,
        scope=ScopeService(employees),
        audit=build_audit_service(session),
        settings=settings or get_settings(),
    )


def build_leave_service(session: AsyncSession) -> LeaveService:
    employees = EmployeeRepository(session)
    return LeaveService(
        leaves=LeaveRepository(session),
        employees=employees,
        scope=ScopeService(employees),
        audit=build_audit_service(session),
    )


def build_dashboard_service(
    session: AsyncSession, settings: Settings | None = None
) -> DashboardService:
    employees = EmployeeRepository(session)
    return DashboardService(
        employees=employees,
        attendance=AttendanceRepository(session),
        leaves=LeaveRepository(session),
        scope=ScopeService(employees),
        settings=settings or get_settings(),
    )


def build_report_service(
    session: AsyncSession, settings: Settings | None = None
) -> ReportService:
    employees = EmployeeRepository(session)
    return ReportService(
        employees=employees,
        attendance=AttendanceRepository(session),
        leaves=LeaveRepository(session),
        exports=ReportExportRepository(session),
        users=UserRepository(session),
        scope=ScopeService(employees),
        audit=build_audit_service(session),
        settings=settings or get_settings(),
    )


def build_health_service(session: AsyncSession) -> HealthService:
    return HealthService(session, get_redis_client())
