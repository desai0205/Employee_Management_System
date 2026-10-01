"""Dashboard counts for the caller's scope."""

from pydantic import BaseModel


class DashboardRead(BaseModel):
    active_employees: int
    employees_on_leave: int
    present_today: int
    pending_leave_requests: int
