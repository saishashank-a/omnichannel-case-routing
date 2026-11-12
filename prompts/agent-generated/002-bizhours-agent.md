# Agent-generated 002 — bizhours.py + tests

- **Tool:** Claude Code sub-agent (Opus 5.5), spawned by the main session
- **Sent:** 2026-11-12 ~08:40 CST (Chicago)

---

Write two files in the repo at /Users/saishashankanchuri/dev/omnichannel-case-routing: `caserouting/bizhours.py` and `tests/test_bizhours.py`. Touch NO other files (other people are editing the rest of the repo in parallel). Do not commit.

Context: a synthetic support-ticket simulator computes SLA deadlines in "business time" on per-channel calendars. Standard library only, Python 3.11+, fully type-hinted, plain code with short comments a candidate must explain line-by-line in an interview — no cleverness, no classes beyond the one NamedTuple.

## Time model
All times are integer minutes since 2026-01-01T00:00Z (UTC, no DST). Day index d = t // 1440. 2026-01-01 is a Thursday; weekday with Monday=0 is `(d + 3) % 7`.

## API (exact names)
```python
class Calendar(NamedTuple):
    name: str
    hours: dict[int, list[tuple[int, int]]]   # weekday (Mon=0) -> sorted, non-overlapping [start_min, end_min) within the day, 0..1440
    holidays: frozenset[int]                   # day indices that are fully closed

def weekday(t: int) -> int
def is_open(cal: Calendar, t: int) -> bool                       # t inside an open segment ([start, end) semantics)
def next_open(cal: Calendar, t: int) -> int                      # t if open, else start of the next open segment
def add_business_minutes(cal: Calendar, t: int, minutes: int) -> int
def business_minutes_between(cal: Calendar, a: int, b: int) -> int   # open minutes in [a, b); 0 if b <= a
def to_iso(t: int) -> str        # "2026-01-03T14:05:00Z"
def from_iso(s: str) -> int
```
Also define `ALWAYS_OPEN = Calendar("24x7", {d: [(0, 1440)] for d in range(7)}, frozenset())`.

## Semantics
- `add_business_minutes(cal, t, m)` returns the earliest T such that `business_minutes_between(cal, t, T) == m`, with these rules: m must be >= 0 (raise ValueError otherwise). If m == 0 return `next_open(cal, t)` (a clock that starts after hours starts at the next open). When the budget is used up exactly at the end of a segment, return that segment end (the close time), NOT the next open.
- Walk day by day and segment by segment — never minute by minute. Guard against calendars with no open time: raise ValueError after scanning 400 days without finding open time.
- Holidays close the whole day regardless of hours.

## Tests (pytest, plain functions, a small table of cases via pytest.mark.parametrize is fine)
Use an example calendar: Mon–Fri 08:00–18:00, holiday = day index 18 (Mon 2026-01-19). Cover:
- weekday(0) == 3 (Thursday)
- arrival inside hours; arrival before open (clock starts at open); arrival after close (next business day); arrival exactly at close (18:00 is closed); exactly at open
- Friday 17:00 + 120 min -> Monday 09:00 (and skips the holiday when that Monday is day 18 -> lands Tuesday)
- budget ending exactly at close returns 18:00 same day
- m == 0 cases
- ALWAYS_OPEN: add == t + m
- round trip property: for a spread of t values (every 97 minutes over 3 weeks) and m in {1, 59, 600, 601, 3000}: `business_minutes_between(cal, t, add_business_minutes(cal, t, m)) == m`
- to_iso/from_iso round trip and to_iso(0) == "2026-01-01T00:00:00Z"
- ValueError on negative minutes and on a calendar with no hours

Run `cd /Users/saishashankanchuri/dev/omnichannel-case-routing && uv run pytest -q tests/test_bizhours.py` until green. Report: the final test count, pass/fail, and any semantic decision you had to make that this brief didn't pin down.
