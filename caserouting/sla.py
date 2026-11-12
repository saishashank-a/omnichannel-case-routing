"""SLA rules: which clock a ticket runs on, its due times, and the SLA records.

Routing calls the due-time helpers (it needs escalate_at). The SLA rows are
built afterwards from the finished event history, so SLA outcomes are pure
functions of recorded facts: rerun this pass and you get the same answer.
"""

from __future__ import annotations

from . import config as C
from . import ids
from .arrivals import channel_calendar
from .bizhours import ALWAYS_OPEN, Calendar, add_business_minutes, next_open


def calendar_for(priority: str, channel: str) -> Calendar:
    """P1 runs 24x7; everything else pauses outside the channel's hours."""
    return ALWAYS_OPEN if priority == "P1" else channel_calendar(channel)


def dues(priority: str, channel: str, start: int) -> dict[str, int]:
    """Due times for a clock started at `start` (arrival, or reopen time).

    A ticket arriving after hours has its clock start at the next open
    minute; add_business_minutes skips closed time on its own.
    """
    cal = calendar_for(priority, channel)
    fr_min, res_min = C.SLA_TARGETS[(priority, channel)]
    return {
        "started_at": next_open(cal, start),
        "first_response_due": add_business_minutes(cal, start, fr_min),
        "resolution_due": add_business_minutes(cal, start, res_min),
        "escalate_at": add_business_minutes(cal, start, int(res_min * C.ESCALATE_AT_FRACTION)),
    }


def build_sla(tickets: list[dict], events: list[dict]) -> tuple[list[dict], list[dict]]:
    """One `sla` header per ticket plus its `sla_event` rows, from the event history.

    Cycle 1 starts at arrival; each REOPEN starts a new cycle with a fresh
    resolution target (CLOCK_RESTARTED). First response is measured once.
    """
    by_ticket: dict[str, list[dict]] = {}
    for e in events:
        by_ticket.setdefault(e["ticket_id"], []).append(e)

    headers, rows = [], []
    for tk in tickets:
        tid, pr, ch = tk["ticket_id"], tk["priority"], tk["channel_id"]
        fr_min, res_min = C.SLA_TARGETS[(pr, ch)]
        d = dues(pr, ch, tk["created_at"])
        headers.append({
            "sla_id": ids.sla_id(tid), "ticket_id": tid, "priority": pr, "channel_id": ch,
            "calendar": "24x7" if pr == "P1" else "CHANNEL",
            "first_response_target_min": fr_min, "resolution_target_min": res_min,
            "started_at": d["started_at"], "first_response_due_at": d["first_response_due"],
            "resolution_due_at": d["resolution_due"],
        })

        out: list[tuple[int, str, int | None, int]] = []   # (ts, event_type, due_at, cycle)
        cycle, res_due = 1, d["resolution_due"]
        out.append((d["started_at"], "CLOCK_STARTED", res_due, cycle))
        if tk["first_response_at"] is not None:
            met = tk["first_response_at"] <= d["first_response_due"]
            out.append((tk["first_response_at"], "FIRST_RESPONSE_MET" if met else "FIRST_RESPONSE_BREACHED",
                        d["first_response_due"], cycle))
        for e in by_ticket.get(tid, []):
            if e["event_type"] == "RESOLVE":
                met = e["ts"] <= res_due
                out.append((e["ts"], "RESOLUTION_MET" if met else "RESOLUTION_BREACHED", res_due, cycle))
            elif e["event_type"] == "REOPEN":
                cycle += 1
                res_due = dues(pr, ch, e["ts"])["resolution_due"]
                out.append((e["ts"], "CLOCK_RESTARTED", res_due, cycle))

        out.sort(key=lambda r: (r[0], r[3]))  # by time; cycle breaks ties
        for seq, (ts, etype, due, cyc) in enumerate(out, start=1):
            rows.append({
                "sla_event_id": ids.sla_event_id(tid, seq), "sla_id": ids.sla_id(tid), "ticket_id": tid,
                "cycle_no": cyc, "event_type": etype, "ts": ts, "due_at": due,
            })
    return headers, rows
