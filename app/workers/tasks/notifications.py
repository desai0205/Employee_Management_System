"""Leave decision notification job is registered from the tasks package."""

from app.workers.tasks import notify_leave_decision

__all__ = ["notify_leave_decision"]
