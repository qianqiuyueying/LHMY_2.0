from __future__ import annotations

from datetime import datetime


def iso(dt: datetime | None) -> str | None:
    """Datetime to ISO8601 string (local tz), None-safe.

    Keep behavior consistent with existing duplicated `_iso` helpers:
    - None => None
    - otherwise => dt.astimezone().isoformat()
    """

    if dt is None:
        return None
    return dt.astimezone().isoformat()


