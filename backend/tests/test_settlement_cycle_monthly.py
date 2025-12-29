from __future__ import annotations

from datetime import UTC, datetime

from app.services.settlement_cycle import compute_settlement_cycle_monthly


def test_compute_settlement_cycle_monthly_formats_yyyy_mm():
    assert compute_settlement_cycle_monthly(dt=datetime(2025, 12, 1, tzinfo=UTC)) == "2025-12"
    assert compute_settlement_cycle_monthly(dt=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)) == "2025-01"
    assert compute_settlement_cycle_monthly(dt=datetime(1999, 9, 10, tzinfo=UTC)) == "1999-09"
