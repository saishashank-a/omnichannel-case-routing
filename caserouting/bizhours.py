"""Business-hours arithmetic on per-channel calendars.

Time is integer minutes since 2026-01-01T00:00Z (UTC, no DST).
Day index d = t // 1440. Day 0 (2026-01-01) is a Thursday.
"""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

MINUTES_PER_DAY = 1440
MAX_EMPTY_DAYS = 400  # give up after this many days in a row with no open time
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Calendar(NamedTuple):
    name: str
    hours: dict[int, list[tuple[int, int]]]  # weekday (Mon=0) -> [start, end) minutes within the day
    holidays: frozenset[int]  # day indices that are fully closed


ALWAYS_OPEN = Calendar("24x7", {d: [(0, 1440)] for d in range(7)}, frozenset())


def weekday(t: int) -> int:
    # Day 0 is a Thursday (Mon=0 -> Thu=3), so shift by 3.
    return (t // MINUTES_PER_DAY + 3) % 7


def _day_segments(cal: Calendar, d: int) -> list[tuple[int, int]]:
    """Open segments of day d as absolute [start, end) minutes. Empty on holidays."""
    if d in cal.holidays:
        return []
    day_start = d * MINUTES_PER_DAY
    hours = cal.hours.get(weekday(day_start), [])
    return [(day_start + s, day_start + e) for s, e in hours]


def is_open(cal: Calendar, t: int) -> bool:
    for start, end in _day_segments(cal, t // MINUTES_PER_DAY):
        if start <= t < end:
            return True
    return False


def next_open(cal: Calendar, t: int) -> int:
    d = t // MINUTES_PER_DAY
    for _ in range(MAX_EMPTY_DAYS):
        for start, end in _day_segments(cal, d):
            if end > t:  # segment not yet over
                return max(t, start)  # already inside it -> t, else its start
        d += 1
    raise ValueError(f"calendar {cal.name!r} has no open time within {MAX_EMPTY_DAYS} days")


def add_business_minutes(cal: Calendar, t: int, minutes: int) -> int:
    if minutes < 0:
        raise ValueError("minutes must be >= 0")
    if minutes == 0:
        return next_open(cal, t)  # clock started after hours starts at the next open

    remaining = minutes
    cur = t  # nothing before cur counts
    d = t // MINUTES_PER_DAY
    empty_days = 0
    while True:
        found_open = False
        for start, end in _day_segments(cal, d):
            if end <= cur:
                continue  # segment already over
            found_open = True
            start = max(start, cur)  # may start mid-segment on the first day
            available = end - start
            if remaining <= available:
                return start + remaining  # == end when budget ends exactly at close
            remaining -= available
        empty_days = 0 if found_open else empty_days + 1
        if empty_days >= MAX_EMPTY_DAYS:
            raise ValueError(f"calendar {cal.name!r} has no open time within {MAX_EMPTY_DAYS} days")
        d += 1
        cur = d * MINUTES_PER_DAY


def business_minutes_between(cal: Calendar, a: int, b: int) -> int:
    if b <= a:
        return 0
    total = 0
    for d in range(a // MINUTES_PER_DAY, (b - 1) // MINUTES_PER_DAY + 1):
        for start, end in _day_segments(cal, d):
            # Overlap of [start, end) with [a, b); negative means no overlap.
            total += max(0, min(end, b) - max(start, a))
    return total


def to_iso(t: int) -> str:
    return (EPOCH + timedelta(minutes=t)).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(s: str) -> int:
    # Seconds below a minute are floored away.
    return (datetime.fromisoformat(s) - EPOCH) // timedelta(minutes=1)
