"""Threaded messages, built from each ticket's event history.

Every ticket gets: the customer's opening message, the first agent reply (at
the first-response time routing decided), a system note per transfer or
escalation, a customer message per reopen, and an agent message per
resolution. A pre-drawn number of extra back-and-forth messages fills the
final assignment of cycle 1. Extras are then nudged up or down, round-robin,
so the total equals the configured target exactly.
"""

from __future__ import annotations

from . import config as C
from . import ids

BODY = {
    "open": "Hello, I need help with {topic}.",
    "first": "Thanks for reaching out about {topic}. I'm looking into it now.",
    "moved": "Your request has been moved to the {queue} team.",
    "reopen": "The {topic} problem is back, it isn't fixed.",
    "resolve": "This is now resolved ({code}). Let us know if anything else comes up.",
    "cust": "Here are more details about my {topic} issue.",
    "agent": "Thanks, I've checked that. One more step on {topic} and we're done.",
}


def _topic(intent: str) -> str:
    return intent.removeprefix("INT-").replace("_", " ").lower()


def _extras_window(evs: list[dict]) -> tuple[int, int, str] | None:
    """(start, end, agent) of the assignment that ends in the first RESOLVE."""
    last_assign = None
    for e in evs:
        if e["event_type"] == "ASSIGN":
            last_assign = e
        elif e["event_type"] == "RESOLVE":
            return last_assign["ts"], e["ts"], last_assign["agent_id"]
    return None


def build_messages(tickets: list[dict], events: list[dict], first_response: dict[str, int],
                   draws: dict[str, dict], target_total: int) -> list[dict]:
    by_ticket: dict[str, list[dict]] = {}
    for e in events:
        by_ticket.setdefault(e["ticket_id"], []).append(e)

    # How many extras each ticket gets, adjusted so the grand total is exact.
    mandatory = {}
    for tk in tickets:
        evs = by_ticket.get(tk["ticket_id"], [])
        mandatory[tk["ticket_id"]] = 2 + sum(e["event_type"] in ("TRANSFER", "ESCALATE", "REOPEN", "RESOLVE")
                                             for e in evs)
    extras = {tk["ticket_id"]: draws[tk["ticket_id"]]["extra_msgs"] for tk in tickets}
    diff = target_total - sum(mandatory.values()) - sum(extras.values())
    if sum(mandatory.values()) > target_total:
        raise ValueError("message target is smaller than the mandatory messages")
    order = [tk["ticket_id"] for tk in tickets]  # already in ticket_id order
    i = 0
    while diff != 0:
        tid = order[i % len(order)]
        if diff > 0 and mandatory[tid] + extras[tid] < C.MAX_MESSAGES_PER_TICKET:
            extras[tid] += 1
            diff -= 1
        elif diff < 0 and extras[tid] > 0:
            extras[tid] -= 1
            diff += 1
        i += 1

    rows: list[dict] = []
    for tk in tickets:
        tid, ch, topic = tk["ticket_id"], tk["channel_id"], _topic(tk["intent_id"])
        evs = by_ticket.get(tid, [])
        first_agent = next(e["agent_id"] for e in evs if e["event_type"] == "ASSIGN")
        # (ts, tie-break order, author, agent, body)
        msgs: list[tuple[int, int, str, str | None, str]] = [
            (tk["created_at"], 0, "CUSTOMER", None, BODY["open"].format(topic=topic)),
            (first_response[tid], 1, "AGENT", first_agent, BODY["first"].format(topic=topic)),
        ]
        for e in evs:
            if e["event_type"] in ("TRANSFER", "ESCALATE"):
                msgs.append((e["ts"], 2, "SYSTEM", None, BODY["moved"].format(queue=e["queue_id"])))
            elif e["event_type"] == "REOPEN":
                msgs.append((e["ts"], 2, "CUSTOMER", None, BODY["reopen"].format(topic=topic)))
            elif e["event_type"] == "RESOLVE":
                msgs.append((e["ts"], 3, "AGENT", e["agent_id"], BODY["resolve"].format(code=e["reason"])))

        window = _extras_window(evs)
        n = extras[tid]
        if window and n:
            start, end, agent = window
            start = max(start, first_response[tid])  # extras come after the first reply
            for k in range(n):
                ts = start + (k + 1) * (end - start) // (n + 1)
                if k % 2 == 0:
                    msgs.append((ts, 1, "CUSTOMER", None, BODY["cust"].format(topic=topic)))
                else:
                    msgs.append((ts, 1, "AGENT", agent, BODY["agent"].format(topic=topic)))
        elif n:
            raise ValueError(f"{tid} has extra messages but was never resolved")

        msgs.sort(key=lambda m: (m[0], m[1]))
        for seq, (ts, _, author, agent, body) in enumerate(msgs, start=1):
            rows.append({"message_id": ids.message_id(tid, seq), "ticket_id": tid, "seq": seq, "ts": ts,
                         "author_type": author, "channel_id": ch, "agent_id": agent, "body": body})
    return rows
