"""Ticket arrivals: when tickets arrive, who sends them, what about, how urgent.

Also pre-draws every random number the later stages need (handle times,
misroutes, reopen draws, CSAT noise...). Drawing everything here, in ticket
order, means routing itself contains no randomness: given these inputs the
simulation is a pure function, which is what makes it reproducible.
"""

from __future__ import annotations

import math
import random

from . import config as C
from . import ids
from .bizhours import Calendar, is_open

PRIORITY_RANK = {p: i for i, p in enumerate(C.PRIORITIES)}  # P1 -> 0 (most urgent)


def channel_calendar(channel: str) -> Calendar:
    return Calendar(channel, C.CHANNELS[channel]["hours"], C.HOLIDAYS)


def assign_priority(intent: str, urgency: str, tier: str | None) -> tuple[str, str]:
    """Apply PRIORITY_RULES in order. Returns (priority, id of last rule that matched)."""
    rank = PRIORITY_RANK[C.INTENTS[intent]["priority"]]
    rule = "PRL-001"                       # intent default
    if urgency == "HIGH" and rank > 0:
        rank, rule = rank - 1, "PRL-002"   # urgency bump
    if tier == "ENTERPRISE" and rank > 0:
        rank, rule = rank - 1, "PRL-003"   # enterprise bump
    if C.INTENTS[intent]["is_safety"]:
        rank, rule = 0, "PRL-005"          # SAFETY RULE: always P1
    elif rank < PRIORITY_RANK["P2"]:
        rank, rule = PRIORITY_RANK["P2"], "PRL-004"  # only safety intents may be P1
    return C.PRIORITIES[rank], rule


def _hour_slots(scale: dict) -> tuple[list[float], set[int]]:
    """Arrival weight for every hour of the horizon, and the set of outage hours."""
    weights, outage = [], set()
    for h in range(scale["days"] * 24):
        day, hod = divmod(h, 24)
        w = C.HOUR_WEIGHTS[hod] * C.WEEKDAY_WEIGHTS[(day + 3) % 7]
        if day in C.HOLIDAYS:
            w *= 0.5                                   # quieter on public holidays
        if day in scale["spike_days"] and C.SPIKE_HOURS[0] <= hod < C.SPIKE_HOURS[1]:
            w *= C.SPIKE_MULTIPLIER                    # queue spike
        if day in scale["outage_days"] and C.OUTAGE_HOURS[0] <= hod < C.OUTAGE_HOURS[1]:
            w *= C.OUTAGE_MULTIPLIER                   # critical incident
            outage.add(h)
        weights.append(w)
    return weights, outage


def _pick(rng: random.Random, shares: dict[str, float]) -> str:
    keys = list(shares)
    return rng.choices(keys, weights=[shares[k] for k in keys], k=1)[0]


def _handle(rng: random.Random, channel: str, factor: float = 1.0) -> int:
    """Minutes an agent slot is held: lognormal around the channel median."""
    median = C.HANDLE_MEDIAN_MIN[channel] * factor
    return max(2, round(rng.lognormvariate(math.log(median), C.HANDLE_SIGMA)))


def build_tickets(seed: int, scale: dict, customers: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Returns (tickets, draws). Ticket times are int minutes; ids follow arrival order."""
    rng = random.Random(f"{seed}:arrivals")
    weights, outage_hours = _hour_slots(scale)
    hours = rng.choices(range(len(weights)), weights=weights, k=scale["tickets"])
    times = sorted(h * 60 + rng.randrange(60) for h in hours)

    sales_intents = {k: v["weight"] for k, v in C.INTENTS.items() if v["queue"] == "QUE-SALES"}
    all_intents = {k: v["weight"] for k, v in C.INTENTS.items()}
    channel_share = {k: v["share"] for k, v in C.CHANNELS.items()}

    tickets = []
    for n, t in enumerate(times, start=1):
        cust = rng.choice(customers)
        channel = _pick(rng, channel_share)
        if t // 60 in outage_hours and rng.random() < C.OUTAGE_INTENT_SHARE:
            intent = "INT-OUTAGE"
        elif cust["customer_type"] == "PROSPECT":
            intent = _pick(rng, sales_intents)          # prospects only ask sales questions
        else:
            intent = _pick(rng, all_intents)
        urgency = "HIGH" if C.INTENTS[intent]["is_safety"] else _pick(rng, C.URGENCY_SHARE)
        priority, rule = assign_priority(intent, urgency, cust["tier"])
        tickets.append({
            "ticket_id": ids.ticket_id(n),
            "customer_id": cust["customer_id"],
            "channel_id": channel,
            "intent_id": intent,
            "language_code": cust["preferred_language"],
            "urgency": urgency,
            "priority": priority,
            "priority_rule_id": rule,
            "created_at": t,
            "after_hours": int(not is_open(channel_calendar(channel), t)),
        })

    # Pre-draws, in ticket order, from their own RNG stream.
    pre = random.Random(f"{seed}:predraw")
    frontline = ["QUE-BILLING", "QUE-ACCOUNT", "QUE-TECH"]
    draws: dict[str, dict] = {}
    for tk in tickets:
        ch = tk["channel_id"]
        correct = C.INTENTS[tk["intent_id"]]["queue"]
        misroute = pre.random() < C.MISROUTE_PROB
        wrong = pre.choice([q for q in frontline if q != correct])
        handle = [_handle(pre, ch), _handle(pre, ch)]          # cycle 1, cycle 2 (after reopen)
        draws[tk["ticket_id"]] = {
            "handle": handle,
            "t2_handle": _handle(pre, ch, C.T2_HANDLE_FACTOR),
            "misroute": misroute,
            "wrong_queue": wrong,
            "discover_frac": pre.uniform(0.2, 0.6),          # when the agent notices the misroute
            "reopen_u": pre.random(),                         # compared against a rule-based probability
            "reopen_delay": pre.randint(*C.REOPEN_DELAY_MIN),
            "csat_responds": pre.random() < C.CSAT_RESPONSE_RATE,
            "csat_noise": pre.choice(C.CSAT_NOISE),
            "extra_msgs": pre.randint(*C.EXTRA_MESSAGES[ch]),
            "resolution_code": pre.choice(["SOLVED", "SOLVED", "SOLVED", "WORKAROUND", "INFO_PROVIDED"]),
        }
    return tickets, draws
