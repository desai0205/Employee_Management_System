"""Import every model so Alembic and the session registry see one metadata object."""

from app.models.attendance import AttendanceRecord
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.models.refresh_token import RefreshToken
from app.models.report_export import ReportExport
from app.models.user import User

__all__ = [
    "AttendanceRecord",
    "AuditLog",
    "Department",
    "Employee",
    "LeaveBalance",
    "LeaveRequest",
    "LeaveType",
    "RefreshToken",
    "ReportExport",
    "User",
]
