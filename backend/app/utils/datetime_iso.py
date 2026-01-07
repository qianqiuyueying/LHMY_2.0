from __future__ import annotations

from datetime import datetime, timezone


def iso(dt: datetime | None) -> str | None:
    """Datetime to ISO8601 UTC string with 'Z' suffix, None-safe.

    Spec:
    - specs/health-services-platform/time-and-timezone.md

    Keep behavior consistent with existing duplicated `_iso` helpers:
    - None => None
    - otherwise => UTC ISO 8601 with Z (seconds precision)
    """

    if dt is None:
        return None

    # DB stores UTC in naive DATETIME; treat naive as UTC.
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=timezone.utc)
    else:
        aware = dt.astimezone(timezone.utc)

    return aware.replace(microsecond=0).isoformat().replace("+00:00", "Z")


