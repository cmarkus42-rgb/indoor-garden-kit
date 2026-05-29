from __future__ import annotations

from datetime import time, timedelta

_DAY = 24 * 60  # minutes in a day


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    m = m % _DAY
    return time(hour=m // 60, minute=m % 60)


def shift_time(t: time, delta: timedelta) -> time:
    m = time_to_minutes(t) + int(delta.total_seconds()) // 60
    return minutes_to_time(m)


def lerp_time(a: time, b: time, t: float) -> time:
    ma = time_to_minutes(a)
    mb = time_to_minutes(b)
    # Handle shortest-path wrapping across midnight
    diff = mb - ma
    if diff > _DAY // 2:
        diff -= _DAY
    elif diff < -_DAY // 2:
        diff += _DAY
    result = ma + round(diff * t)
    return minutes_to_time(result)
