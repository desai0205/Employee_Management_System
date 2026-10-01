"""Clock helpers. Business dates use the organization timezone."""

from datetime import UTC, datetime
from datetime import time as time_of_day
from zoneinfo import ZoneInfo

from app.core.config import Settings, get_settings


def utc_now() -> datetime:
    return datetime.now(UTC)


def zone(settings: Settings | None = None) -> ZoneInfo:
    current = settings or get_settings()
    return ZoneInfo(current.org_timezone)


def org_now(settings: Settings | None = None) -> datetime:
    return datetime.now(zone(settings))


def attendance_start(settings: Settings | None = None) -> time_of_day:
    current = settings or get_settings()
    hour, minute = current.attendance_start_time.split(":")
    return time_of_day(int(hour), int(minute))
