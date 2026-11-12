"""Routing simulation: assigns tickets to agents over time.

How it works:
- A heap holds "this ticket needs an agent at time t" requests, ordered by
  time, then priority (P1 first), then a counter (so ties are deterministic).
- An agent is eligible when they are on shift, have the queue's skill, speak
  the ticket's language, and are below their concurrency limit for the
  ticket's channel. If no on-shift agent with the skill speaks the language,
  any of them may take it with translation_flag=1 (the language-mismatch path).
- Among free eligible agents, pick the least loaded, then lowest agent_id.
- No free agent: retry in RETRY_TICK_MIN minutes, or exactly at the escalation
  point if that comes first, or at the next shift start if nobody is on shift.
- On assignment, the slot ends at the earliest of: misroute discovered
  (TRANSFER), 80% of the resolution SLA used (ESCALATE), or work done
  (RESOLVE). Every step is appended to assignment_event; nothing is updated.

There is no randomness in here: every random input was pre-drawn in arrivals.
Limitation: priority only orders requests that retry at the same minute;
a waiting P4 is not pre-empted by a later P1.
"""

from __future__ import annotations

import heapq

from . import config as C
from . import ids
from .arrivals import PRIORITY_RANK
from .bizhours import weekday
from .sla import dues

ESC = C.ESCALATION_QUEUE


def on_shift(shift: dict, t: int) -> bool:
    """Is minute t inside this shift? Night shift wraps past midnight."""
    m = t % C.DAY
    if shift["start"] < shift["end"]:
        return shift["start"] <= m < shift["end"] and weekday(t) in shift["weekdays"]
    if m >= shift["start"]:                       # evening part of a wrapping shift
        return weekday(t) in shift["weekdays"]
    if m < shift["end"]:                          # morning part belongs to yesterday's shift
        return weekday(t - C.DAY) in shift["weekdays"]
    return False


def next_shift_start(shift: dict, t: int) -> int:
    """First minute after t at which this shift is on."""
    day = t // C.DAY
    for d in range(day, day + 8):
        start = d * C.DAY + shift["start"]
        if start > t and weekday(start) in shift["weekdays"]:
            return start
    raise ValueError("shift never starts")


def simulate(tickets: list[dict], draws: dict[str, dict], master: dict, horizon_end: int) -> dict:
    """Run the simulation. Returns assignment events, resolutions and first-response times."""
    # --- agent lookup tables -------------------------------------------------
    langs: dict[str, set[str]] = {}
    for r in master["agent_language"]:
        langs.setdefault(r["agent_id"], set()).add(r["language_code"])
    agents = {
        a["agent_id"]: {
            "id": a["agent_id"],
            "shift": C.SHIFTS[a["shift_id"]],
            "langs": langs[a["agent_id"]],
            "limit": {"EMAIL": a["max_concurrent_email"], "CHAT": a["max_concurrent_chat"],
                      "PHONE": a["max_concurrent_phone"]},
        }
        for a in master["agent"]
    }
    by_skill: dict[str, list[dict]] = {}
    for r in sorted(master["agent_skill"], key=lambda r: r["agent_id"]):
        by_skill.setdefault(r["skill_id"], []).append(agents[r["agent_id"]])

    busy: dict[tuple[str, str], list[int]] = {}   # (agent, channel) -> slot release times

    def active(agent_id: str, channel: str, t: int) -> int:
        # A slot released at exactly t is free at t (release before assign).
        key = (agent_id, channel)
        busy[key] = [r for r in busy.get(key, []) if r > t]
        return len(busy[key])

    # --- per-ticket simulation state ----------------------------------------
    tk_by_id = {tk["ticket_id"]: tk for tk in tickets}
    state: dict[str, dict] = {}
    for tk in tickets:
        dr = draws[tk["ticket_id"]]
        d = dues(tk["priority"], tk["channel_id"], tk["created_at"])
        home = C.INTENTS[tk["intent_id"]]["queue"]
        state[tk["ticket_id"]] = {
            "queue": dr["wrong_queue"] if dr["misroute"] else home,
            "home": home, "cycle": 1, "escalated": False, "transferred": False,
            "esc_at": d["escalate_at"], "res_due": d["resolution_due"], "seq": 0,
        }

    events: list[dict] = []
    resolutions: list[dict] = []
    first_response: dict[str, int] = {}
    heap: list[tuple[int, int, int, str]] = []
    counter = 0

    def push(t: int, tid: str) -> None:
        nonlocal counter
        counter += 1
        heapq.heappush(heap, (t, PRIORITY_RANK[tk_by_id[tid]["priority"]], counter, tid))

    def emit(tid: str, etype: str, ts: int, queue: str, agent: str | None, translated: int, reason: str) -> None:
        st = state[tid]
        st["seq"] += 1
        events.append({
            "asn_id": ids.assignment_id(tid, st["seq"]), "ticket_id": tid, "seq": st["seq"],
            "event_type": etype, "ts": ts, "queue_id": queue, "agent_id": agent,
            "translation_flag": translated, "reason": reason,
        })

    def can_escalate(st: dict) -> bool:
        return not st["escalated"] and st["queue"] != ESC

    def route(t: int, tid: str) -> None:
        tk, st, dr = tk_by_id[tid], state[tid], draws[tid]
        ch = tk["channel_id"]

        # 1. A waiting ticket that reached its escalation point moves to Tier-2.
        if can_escalate(st) and t >= st["esc_at"]:
            emit(tid, "ESCALATE", st["esc_at"], ESC, None, 0, "80% of resolution SLA used while queued")
            st["escalated"], st["queue"] = True, ESC

        # 2. Find eligible agents.
        on = [a for a in by_skill.get(C.QUEUES[st["queue"]]["skill"], []) if on_shift(a["shift"], t)]
        speakers = [a for a in on if tk["language_code"] in a["langs"]]
        pool, translated = (speakers, 0) if speakers else (on, 1)
        free = [a for a in pool if active(a["id"], ch, t) < a["limit"][ch]]

        if not free:
            if on:
                retry = t + C.RETRY_TICK_MIN
            else:  # nobody with this skill is on shift: wait for the next shift start
                skill_agents = by_skill.get(C.QUEUES[st["queue"]]["skill"], [])
                retry = min(next_shift_start(a["shift"], t) for a in skill_agents)
            if can_escalate(st):
                retry = min(retry, st["esc_at"])
            push(retry, tid)
            return

        agent = min(free, key=lambda a: (active(a["id"], ch, t) / a["limit"][ch], a["id"]))
        reason = "skill and language match" if not translated else \
            f"skill match; no on-shift agent speaks {tk['language_code']}, translation used"
        emit(tid, "ASSIGN", t, st["queue"], agent["id"], translated, reason)

        # 3. Decide how this slot ends: transfer, escalation or resolution, whichever is first.
        handle = dr["t2_handle"] if st["queue"] == ESC else dr["handle"][st["cycle"] - 1]
        options = [(t + handle, 2, "RESOLVE")]
        if st["cycle"] == 1 and st["queue"] == dr["wrong_queue"] and dr["misroute"] and not st["transferred"]:
            options.append((t + max(1, int(handle * dr["discover_frac"])), 0, "TRANSFER"))
        if can_escalate(st):
            options.append((st["esc_at"], 1, "ESCALATE"))
        end, _, outcome = min(options)
        busy.setdefault((agent["id"], ch), []).append(end)

        if tid not in first_response:  # first agent reply, never after the slot ends
            first_response[tid] = min(t + max(1, int(handle * C.FIRST_RESPONSE_FRACTION)), end)

        if outcome == "TRANSFER":
            emit(tid, "TRANSFER", end, st["home"], None, 0, f"misrouted to {st['queue']}; moved to {st['home']}")
            st["queue"], st["transferred"] = st["home"], True
            push(end, tid)
        elif outcome == "ESCALATE":
            emit(tid, "ESCALATE", end, ESC, None, 0, "80% of resolution SLA used while assigned")
            st["escalated"], st["queue"] = True, ESC
            push(end, tid)
        else:
            emit(tid, "RESOLVE", end, st["queue"], agent["id"], 0, dr["resolution_code"])
            resolutions.append({
                "resolution_id": ids.resolution_id(tid, st["cycle"]), "ticket_id": tid,
                "cycle_no": st["cycle"], "agent_id": agent["id"], "resolved_at": end,
                "handle_minutes": end - t, "resolution_code": dr["resolution_code"], "csat": None,
            })
            # Reopen by rule: probability rises if the SLA was breached or the ticket was transferred.
            p = C.REOPEN_BASE_PROB + C.REOPEN_IF_BREACHED * (end > st["res_due"]) \
                + C.REOPEN_IF_TRANSFERRED * st["transferred"]
            reopen_at = end + dr["reopen_delay"]
            if st["cycle"] == 1 and dr["reopen_u"] < p and reopen_at < horizon_end:
                emit(tid, "REOPEN", reopen_at, st["queue"], None, 0, "customer reports the issue persists")
                d = dues(tk["priority"], ch, reopen_at)
                st["cycle"], st["esc_at"], st["res_due"] = 2, d["escalate_at"], d["resolution_due"]
                push(reopen_at, tid)

    for tk in tickets:
        push(tk["created_at"], tk["ticket_id"])
    while heap:
        t, _, _, tid = heapq.heappop(heap)
        route(t, tid)

    return {"assignment_event": events, "resolution": resolutions, "first_response": first_response}
