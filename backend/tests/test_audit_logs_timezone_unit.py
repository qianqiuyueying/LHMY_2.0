from __future__ import annotations

from datetime import date, datetime, timezone

from app.api.v1.audit_logs import _beijing_day_range_to_utc_naive, _iso_utc_z


def test_iso_utc_z_from_naive_dt_treated_as_utc() -> None:
    # DB stores UTC in naive DATETIME
    dt = datetime(2026, 1, 7, 12, 34, 56)  # naive UTC
    assert _iso_utc_z(dt) == "2026-01-07T12:34:56Z"


def test_iso_utc_z_from_aware_dt_converted_to_utc() -> None:
    dt = datetime(2026, 1, 7, 20, 34, 56, tzinfo=timezone.utc)
    assert _iso_utc_z(dt) == "2026-01-07T20:34:56Z"


def test_beijing_day_range_converted_to_utc_naive() -> None:
    # Beijing 2026-01-07 00:00:00+08:00 == 2026-01-06 16:00:00Z
    # EndExclusive is next day 00:00+08 == 2026-01-07 16:00:00Z
    start, end_excl = _beijing_day_range_to_utc_naive(date(2026, 1, 7))
    assert start == datetime(2026, 1, 6, 16, 0, 0)
    assert end_excl == datetime(2026, 1, 7, 16, 0, 0)


