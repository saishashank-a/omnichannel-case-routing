import pytest

from caserouting.bizhours import (
    ALWAYS_OPEN,
    Calendar,
    add_business_minutes,
    business_minutes_between,
    from_iso,
    is_open,
    next_open,
    to_iso,
    weekday,
)

# Mon-Fri 08:00-18:00, Mon 2026-01-19 (day 18) is a holiday.
CAL = Calendar("office", {d: [(8 * 60, 18 * 60)] for d in range(5)}, frozenset({18}))


def at(day: int, hh: int, mm: int = 0) -> int:
    return day * 1440 + hh * 60 + mm


def test_weekday_epoch_is_thursday() -> None:
    assert weekday(0) == 3
    assert weekday(at(4, 12)) == 0  # 2026-01-05 is a Monday


@pytest.mark.parametrize(
    ("t", "open_", "nxt"),
    [
        (at(5, 10), True, at(5, 10)),  # Tue 10:00 inside hours
        (at(5, 7), False, at(5, 8)),  # before open
        (at(5, 19), False, at(6, 8)),  # after close -> next day
        (at(5, 18), False, at(6, 8)),  # exactly at close is closed
        (at(5, 8), True, at(5, 8)),  # exactly at open
        (at(1, 18), False, at(4, 8)),  # Fri close -> Mon open
        (at(15, 18), False, at(19, 8)),  # Fri close -> skip holiday Mon -> Tue
    ],
)
def test_is_open_and_next_open(t: int, open_: bool, nxt: int) -> None:
    assert is_open(CAL, t) is open_
    assert next_open(CAL, t) == nxt


@pytest.mark.parametrize(
    ("t", "m", "expected"),
    [
        (at(5, 10), 60, at(5, 11)),  # inside hours
        (at(5, 7), 60, at(5, 9)),  # before open: clock starts at 08:00
        (at(5, 19), 60, at(6, 9)),  # after close: next business day
        (at(5, 18), 60, at(6, 9)),  # exactly at close
        (at(5, 8), 60, at(5, 9)),  # exactly at open
        (at(1, 17), 120, at(4, 9)),  # Fri 17:00 + 2h -> Mon 09:00
        (at(15, 17), 120, at(19, 9)),  # same, but Mon is a holiday -> Tue
        (at(5, 17), 60, at(5, 18)),  # budget ends exactly at close -> 18:00
        (at(5, 8), 600, at(5, 18)),  # full day ends at close
        (at(5, 10), 0, at(5, 10)),  # m == 0 while open
        (at(5, 19), 0, at(6, 8)),  # m == 0 after hours -> next open
        (at(5, 18), 0, at(6, 8)),  # m == 0 at close -> next open
    ],
)
def test_add_business_minutes(t: int, m: int, expected: int) -> None:
    assert add_business_minutes(CAL, t, m) == expected


@pytest.mark.parametrize("t", [0, 1, 777, at(10, 23, 59)])
@pytest.mark.parametrize("m", [0, 1, 1440, 10_000])
def test_always_open(t: int, m: int) -> None:
    assert add_business_minutes(ALWAYS_OPEN, t, m) == t + m


def test_between_basics() -> None:
    assert business_minutes_between(CAL, at(5, 10), at(5, 10)) == 0
    assert business_minutes_between(CAL, at(5, 12), at(5, 10)) == 0
    assert business_minutes_between(CAL, at(1, 17), at(4, 9)) == 120
    assert business_minutes_between(CAL, at(15, 0), at(20, 0)) == 1200  # Fri + Tue, holiday skipped


@pytest.mark.parametrize("m", [1, 59, 600, 601, 3000])
def test_round_trip_property(m: int) -> None:
    for t in range(0, 3 * 7 * 1440, 97):
        end = add_business_minutes(CAL, t, m)
        assert business_minutes_between(CAL, t, end) == m, (t, m)
        # Earliest such T: one minute less would fall short.
        assert business_minutes_between(CAL, t, end - 1) == m - 1, (t, m)


def test_iso_round_trip() -> None:
    assert to_iso(0) == "2026-01-01T00:00:00Z"
    assert to_iso(at(2, 14, 5)) == "2026-01-03T14:05:00Z"
    for t in [0, 1, 59, 1439, 1440, at(18, 8), 525_600]:
        assert from_iso(to_iso(t)) == t


def test_negative_minutes_raises() -> None:
    with pytest.raises(ValueError):
        add_business_minutes(CAL, 0, -1)


def test_no_hours_calendar_raises() -> None:
    closed = Calendar("closed", {}, frozenset())
    with pytest.raises(ValueError):
        add_business_minutes(closed, 0, 10)
    with pytest.raises(ValueError):
        next_open(closed, 0)
