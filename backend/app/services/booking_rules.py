"""预约规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 18：预约取消时间窗口

约束：
- v1 以 bookingDate + timeSlot 派生开始时间。
- bookingDate 口径为本地日期（Asia/Shanghai）；此处使用 naive datetime 表示“同一时区”的本地时间。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re

_TIME_SLOT_RE = re.compile(r"^(?P<sh>\d{2}):(?P<sm>\d{2})-(?P<eh>\d{2}):(?P<em>\d{2})$")


@dataclass(frozen=True)
class TimeSlot:
    start: time
    end: time


def parse_time_slot(time_slot: str) -> TimeSlot:
    """解析 'HH:mm-HH:mm' 时段字符串。"""

    m = _TIME_SLOT_RE.match(time_slot)
    if not m:
        raise ValueError("invalid timeSlot format")

    sh = int(m.group("sh"))
    sm = int(m.group("sm"))
    eh = int(m.group("eh"))
    em = int(m.group("em"))

    try:
        start = time(hour=sh, minute=sm)
        end = time(hour=eh, minute=em)
    except ValueError as e:
        raise ValueError("invalid timeSlot value") from e

    if (eh, em) <= (sh, sm):
        raise ValueError("timeSlot end must be after start")

    return TimeSlot(start=start, end=end)


def booking_start_datetime(booking_date: date, time_slot: str) -> datetime:
    """由 bookingDate 与 timeSlot 派生预约开始时间（naive 本地时间）。"""

    ts = parse_time_slot(time_slot)
    return datetime.combine(booking_date, ts.start)


def can_cancel_confirmed_booking(*, booking_date: date, time_slot: str, now: datetime) -> bool:
    """是否允许取消已确认预约（属性18）。

    规则：距开始时间 >= 2小时（含）允许；<2小时拒绝。
    """

    start_dt = booking_start_datetime(booking_date, time_slot)
    return start_dt - now >= timedelta(hours=2)
