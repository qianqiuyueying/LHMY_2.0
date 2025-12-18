"""属性测试：预约取消时间窗口（属性18）。

规格来源：
- specs/health-services-platform/design.md -> 属性 18：预约取消时间窗口

断言：
- 对于任意“已确认预约”，当 now 距开始时间 >= 2h（含）允许取消；<2h 不允许。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from app.services.booking_rules import can_cancel_confirmed_booking


@st.composite
def _booking_case(draw):
    # 构造同一天内的合法时段：开始小时 0~22，结束=开始+1h
    y = draw(st.integers(min_value=2020, max_value=2035))
    m = draw(st.integers(min_value=1, max_value=12))
    d = draw(st.integers(min_value=1, max_value=28))

    start_hour = draw(st.integers(min_value=0, max_value=22))
    start_minute = draw(st.integers(min_value=0, max_value=59))

    start_dt = datetime(y, m, d, start_hour, start_minute, 0)

    booking_date = start_dt.date()
    time_slot = f"{start_hour:02d}:{start_minute:02d}-{(start_hour + 1):02d}:{start_minute:02d}"

    # diff_seconds = start - now
    diff_seconds = draw(st.integers(min_value=-24 * 3600, max_value=24 * 3600))
    now = start_dt - timedelta(seconds=diff_seconds)

    return booking_date, time_slot, now, diff_seconds


@given(_booking_case())
def test_property_18_booking_cancel_window(case):
    booking_date, time_slot, now, diff_seconds = case

    expected = diff_seconds >= 2 * 3600
    assert can_cancel_confirmed_booking(booking_date=booking_date, time_slot=time_slot, now=now) == expected
