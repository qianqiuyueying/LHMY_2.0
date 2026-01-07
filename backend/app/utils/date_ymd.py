from __future__ import annotations

from datetime import date, datetime, timezone


def ymd(value: date | datetime | None) -> str | None:
    """Date-like value to YYYY-MM-DD string, None-safe.

    Spec:
    - specs/health-services-platform/time-and-timezone.md

    Notes:
    - For naive datetimes (e.g., MySQL DATETIME), treat as UTC and take its date component.
    - For aware datetimes, convert to UTC before taking date to avoid environment-dependent tz.
    """

    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()

    dt = value
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.date().isoformat()


