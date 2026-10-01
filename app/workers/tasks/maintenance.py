"""Scheduled maintenance jobs are registered from the tasks package."""

from app.workers.tasks import mark_missing_attendance, purge_expired_refresh_tokens

__all__ = ["mark_missing_attendance", "purge_expired_refresh_tokens"]
