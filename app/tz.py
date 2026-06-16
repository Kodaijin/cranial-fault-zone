"""Application timezone: fixed GMT-8 (no DST).

Timestamps are stored in UTC; this module governs how they are bucketed into
calendar days (grids, streaks, date-range filtering) so that the end of a day is
midnight GMT-8.
"""
from datetime import date, datetime, timedelta, timezone

APP_TZ = timezone(timedelta(hours=-8))  # GMT-8, fixed (no daylight saving)


def app_now() -> datetime:
    return datetime.now(APP_TZ)


def app_today() -> date:
    return datetime.now(APP_TZ).date()


def to_app_date(dt: datetime) -> date:
    """Calendar date of `dt` in GMT-8. Naive datetimes are assumed to be UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TZ).date()


def to_app_datetime(dt: datetime) -> datetime:
    """Localize `dt` to GMT-8 (for local hour/weekday). Naive = UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TZ)
