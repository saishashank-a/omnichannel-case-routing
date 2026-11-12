"""Derived values. Nothing here is drawn at random on its own: every column is
computed from recorded events plus a documented rule.

Ticket snapshot columns (status, current queue, counts, first response,
resolved time) summarise the append-only event history; they are recomputed,
never edited.
"""

from __future__ import annotations

from . import config as C

STATUS_AFTER = {"ASSIGN": "ASSIGNED", "TRANSFER": "QUEUED", "ESCALATE": "QUEUED",
                "RESOLVE": "RESOLVED", "REOPEN": "REOPENED"}


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ticket_id"], []).append(r)
    return out


def derive_ticket_columns(tickets: list[dict], events: list[dict], messages: list[dict]) -> None:
    """Fill the snapshot columns on each ticket from its events and messages."""
    ev, msg = _group(events), _group(messages)
    for tk in tickets:
        evs = ev.get(tk["ticket_id"], [])
        last = evs[-1] if evs else None
        tk["status"] = STATUS_AFTER[last["event_type"]] if last else "QUEUED"
        tk["current_queue_id"] = last["queue_id"] if last else C.INTENTS[tk["intent_id"]]["queue"]
        tk["transfer_count"] = sum(e["event_type"] == "TRANSFER" for e in evs)
        tk["escalation_count"] = sum(e["event_type"] == "ESCALATE" for e in evs)
        tk["reopen_count"] = sum(e["event_type"] == "REOPEN" for e in evs)
        agent_msgs = [m["ts"] for m in msg.get(tk["ticket_id"], []) if m["author_type"] == "AGENT"]
        tk["first_response_at"] = min(agent_msgs) if agent_msgs else None
        tk["resolved_at"] = last["ts"] if last and last["event_type"] == "RESOLVE" else None


def csat_score(breached: bool, transfers: int, reopened: bool, wait_min: int, noise: int) -> int:
    """CSAT rule (documented in README): start at 5 and subtract for each bad experience."""
    wait_penalty = min(1.5, C.CSAT_WAIT_PENALTY_PER_HOUR * wait_min / 60)
    raw = 5 - 1.5 * breached - 0.5 * transfers - 1.0 * reopened - wait_penalty + noise
    return max(1, min(5, round(raw)))


def apply_csat(tickets: list[dict], events: list[dict], sla_events: list[dict],
               resolutions: list[dict], draws: dict[str, dict]) -> None:
    """CSAT on the final resolution of each resolved ticket, if the customer answered the survey."""
    ev, sla, res = _group(events), _group(sla_events), _group(resolutions)
    for tk in tickets:
        tid = tk["ticket_id"]
        tk["csat"] = None
        if tk["status"] != "RESOLVED" or not draws[tid]["csat_responds"]:
            continue
        first_assign = next(e["ts"] for e in ev[tid] if e["event_type"] == "ASSIGN")
        breached = any(s["event_type"] == "RESOLUTION_BREACHED" for s in sla.get(tid, []))
        score = csat_score(breached, tk["transfer_count"], tk["reopen_count"] > 0,
                           first_assign - tk["created_at"], draws[tid]["csat_noise"])
        tk["csat"] = score
        res[tid][-1]["csat"] = score  # resolution rows are in cycle order
