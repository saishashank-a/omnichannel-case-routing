"""Validation: re-checks an exported dataset from its files alone.

It never reads ground truth or generator state. Two kinds of checks:

Structural (should always be 0 failures): primary-key uniqueness, foreign
keys, enums, ID formats, date ordering, duplicates, arithmetic
reconciliation of derived columns.

Business rules (findings are tagged with an issue_type): routing
eligibility, capacity, SLA due dates and outcomes, escalation timing,
assignment-history completeness, lifecycle transitions, transfer loops and
the priority safety rule. On the clean baseline these produce 0 findings;
after injection they should find exactly the labelled tickets.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from . import config as C
from . import ids
from .bizhours import from_iso
from .export import schema_columns
from .routing import on_shift
from .sla import dues

ANOMALY_TYPES = set(C.ANOMALY_TYPES)

# Which event may follow which ticket state (see docs/model.md).
TRANSITIONS = {
    "ASSIGN": ({"QUEUED", "REOPENED"}, "ASSIGNED"),
    "TRANSFER": ({"ASSIGNED", "QUEUED"}, "QUEUED"),
    "ESCALATE": ({"ASSIGNED", "QUEUED", "REOPENED"}, "QUEUED"),
    "RESOLVE": ({"ASSIGNED"}, "RESOLVED"),
    "REOPEN": ({"RESOLVED"}, "REOPENED"),
}

ENUMS = {
    ("ticket", "channel_id"): set(C.CHANNELS),
    ("ticket", "urgency"): set(C.URGENCY_SHARE),
    ("ticket", "priority"): set(C.PRIORITIES),
    ("ticket", "status"): {"QUEUED", "ASSIGNED", "RESOLVED", "REOPENED"},
    ("ticket", "after_hours"): {0, 1},
    ("assignment_event", "event_type"): set(TRANSITIONS),
    ("assignment_event", "translation_flag"): {0, 1},
    ("sla_event", "event_type"): {"CLOCK_STARTED", "FIRST_RESPONSE_MET", "FIRST_RESPONSE_BREACHED",
                                  "RESOLUTION_MET", "RESOLUTION_BREACHED", "CLOCK_RESTARTED"},
    ("message", "author_type"): {"CUSTOMER", "AGENT", "SYSTEM"},
    ("customer", "customer_type"): {"CUSTOMER", "PROSPECT"},
}

# (child table, column, parent table, parent column)
FOREIGN_KEYS = [
    ("queue", "skill_id", "skill", "skill_id"),
    ("intent", "queue_id", "queue", "queue_id"),
    ("customer", "preferred_language", "language", "language_code"),
    ("agent", "shift_id", "shift", "shift_id"),
    ("agent_skill", "agent_id", "agent", "agent_id"),
    ("agent_skill", "skill_id", "skill", "skill_id"),
    ("agent_language", "agent_id", "agent", "agent_id"),
    ("agent_language", "language_code", "language", "language_code"),
    ("ticket", "customer_id", "customer", "customer_id"),
    ("ticket", "channel_id", "channel", "channel_id"),
    ("ticket", "intent_id", "intent", "intent_id"),
    ("ticket", "language_code", "language", "language_code"),
    ("ticket", "priority_rule_id", "priority_rule", "rule_id"),
    ("ticket", "current_queue_id", "queue", "queue_id"),
    ("sla", "ticket_id", "ticket", "ticket_id"),
    ("assignment_event", "ticket_id", "ticket", "ticket_id"),
    ("assignment_event", "queue_id", "queue", "queue_id"),
    ("assignment_event", "agent_id", "agent", "agent_id"),
    ("sla_event", "sla_id", "sla", "sla_id"),
    ("sla_event", "ticket_id", "ticket", "ticket_id"),
    ("message", "ticket_id", "ticket", "ticket_id"),
    ("message", "agent_id", "agent", "agent_id"),
    ("resolution", "ticket_id", "ticket", "ticket_id"),
    ("resolution", "agent_id", "agent", "agent_id"),
]

ID_COLUMNS = {("ticket", "ticket_id"): "ticket_id", ("customer", "customer_id"): "customer_id",
              ("agent", "agent_id"): "agent_id", ("message", "message_id"): "message_id",
              ("assignment_event", "asn_id"): "asn_id", ("sla", "sla_id"): "sla_id",
              ("sla_event", "sla_event_id"): "sla_event_id", ("resolution", "resolution_id"): "resolution_id"}


def load_dir(data_dir: Path) -> dict[str, list[dict]]:
    return {t: json.loads((data_dir / "json" / f"{t}.json").read_text(encoding="utf-8"))
            for t in schema_columns()}


def _t(v: str | None) -> int | None:
    return None if v is None else from_iso(v)


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ticket_id"], []).append(r)
    return out


def structural_checks(db: dict[str, list[dict]]) -> list[dict]:
    """Return a list of {check, table, detail} failures."""
    fails: list[dict] = []

    def fail(check: str, table: str, detail: str) -> None:
        fails.append({"check": check, "table": table, "detail": detail})

    # Primary keys unique and non-null.
    for table, (_, pk) in schema_columns().items():
        keys = Counter(tuple(r[c] for c in pk) for r in db[table])
        for k, n in keys.items():
            if n > 1 or None in k:
                fail("pk_unique", table, f"{k} appears {n}x")

    # Foreign keys resolve (nullable FKs may be null).
    for child, col, parent, pcol in FOREIGN_KEYS:
        parents = {r[pcol] for r in db[parent]}
        for r in db[child]:
            if r[col] is not None and r[col] not in parents:
                fail("fk_integrity", child, f"{col}={r[col]} not in {parent}")

    # Enums and ID formats.
    for (table, col), allowed in ENUMS.items():
        for r in db[table]:
            if r[col] not in allowed:
                fail("enum", table, f"{col}={r[col]!r}")
    for (table, col), pattern in ID_COLUMNS.items():
        for r in db[table]:
            if not ids.PATTERNS[pattern].match(r[col]):
                fail("id_format", table, f"{col}={r[col]}")
    for r in db["ticket"]:
        if r["csat"] is not None and not 1 <= r["csat"] <= 5:
            fail("range", "ticket", f"{r['ticket_id']} csat={r['csat']}")

    # Date ordering.
    tickets = {r["ticket_id"]: r for r in db["ticket"]}
    customers = {r["customer_id"]: r for r in db["customer"]}
    for tk in db["ticket"]:
        created = _t(tk["created_at"])
        if _t(customers[tk["customer_id"]]["created_at"]) > created:
            fail("date_order", "ticket", f"{tk['ticket_id']} created before its customer")
        for col in ("first_response_at", "resolved_at"):
            if tk[col] is not None and _t(tk[col]) < created:
                fail("date_order", "ticket", f"{tk['ticket_id']} {col} before created_at")
    for table in ("assignment_event", "message", "sla_event"):
        for tid, rows in _group(db[table]).items():
            created = _t(tickets[tid]["created_at"])
            prev = None
            for r in sorted(rows, key=lambda r: r["seq"] if "seq" in r else r[next(iter(r))]):
                ts = _t(r["ts"])
                if ts < created:
                    fail("date_order", table, f"{tid} event before ticket created")
                if table != "sla_event" and prev is not None and ts < prev:
                    fail("date_order", table, f"{tid} seq order is not time order")
                prev = ts

    # Duplicates on natural keys (beyond the PK).
    for table, key in (("ticket", ("customer_id", "created_at", "channel_id", "intent_id")),
                       ("assignment_event", ("ticket_id", "event_type", "ts", "queue_id", "agent_id", "reason")),
                       ("resolution", ("ticket_id", "resolved_at"))):
        for k, n in Counter(tuple(r[c] for c in key) for r in db[table]).items():
            if n > 1:
                fail("duplicate", table, f"{key}={k} appears {n}x")

    # Arithmetic reconciliation: snapshot columns equal what the events say.
    ev, msg, res, sla_ev = (_group(db[t]) for t in ("assignment_event", "message", "resolution", "sla_event"))
    status_after = {e: s for e, (_, s) in TRANSITIONS.items()}
    for tk in db["ticket"]:
        tid = tk["ticket_id"]
        evs = sorted(ev.get(tid, []), key=lambda e: e["seq"])
        counts = Counter(e["event_type"] for e in evs)
        expect = {
            "transfer_count": counts["TRANSFER"], "escalation_count": counts["ESCALATE"],
            "reopen_count": counts["REOPEN"],
            "status": status_after[evs[-1]["event_type"]] if evs else "QUEUED",
            "resolved_at": evs[-1]["ts"] if evs and evs[-1]["event_type"] == "RESOLVE" else None,
            "first_response_at": min((m["ts"] for m in msg.get(tid, []) if m["author_type"] == "AGENT"),
                                     key=from_iso, default=None),
        }
        if evs:
            expect["current_queue_id"] = evs[-1]["queue_id"]
        for col, val in expect.items():
            if tk[col] != val:
                fail("reconciliation", "ticket", f"{tid} {col}={tk[col]} but events say {val}")
        if len(res.get(tid, [])) != counts["RESOLVE"]:
            fail("reconciliation", "resolution", f"{tid} has {len(res.get(tid, []))} resolutions, "
                                                  f"{counts['RESOLVE']} RESOLVE events")
        cycles = {s["cycle_no"] for s in sla_ev.get(tid, [])}
        if cycles and max(cycles) != counts["REOPEN"] + 1:
            fail("reconciliation", "sla_event", f"{tid} has {max(cycles)} SLA cycles, {counts['REOPEN']} reopens")
    for r in db["resolution"]:
        assigns = [e for e in ev.get(r["ticket_id"], []) if e["event_type"] == "ASSIGN"
                   and from_iso(e["ts"]) <= from_iso(r["resolved_at"])]
        if assigns and from_iso(r["resolved_at"]) - from_iso(assigns[-1]["ts"]) != r["handle_minutes"]:
            fail("reconciliation", "resolution", f"{r['resolution_id']} handle_minutes mismatch")
    return fails


def business_checks(db: dict[str, list[dict]]) -> list[dict]:
    """Return findings {issue_type, ticket_id, check, detail}."""
    found: list[dict] = []

    def flag(issue: str, tid: str, check: str, detail: str) -> None:
        found.append({"issue_type": issue, "ticket_id": tid, "check": check, "detail": detail})

    tickets = {r["ticket_id"]: r for r in db["ticket"]}
    shifts = {s["shift_id"]: {"start": s["start_min"], "end": s["end_min"],
                              "weekdays": [int(d) for d in s["weekdays"].split(",")]} for s in db["shift"]}
    agents = {a["agent_id"]: a for a in db["agent"]}
    skills: dict[str, set[str]] = {}
    for r in db["agent_skill"]:
        skills.setdefault(r["agent_id"], set()).add(r["skill_id"])
    langs: dict[str, set[str]] = {}
    for r in db["agent_language"]:
        langs.setdefault(r["agent_id"], set()).add(r["language_code"])
    queue_skill = {q["queue_id"]: q["skill_id"] for q in db["queue"]}
    is_safety = {i["intent_id"]: i["is_safety"] for i in db["intent"]}
    limit_col = {"EMAIL": "max_concurrent_email", "CHAT": "max_concurrent_chat", "PHONE": "max_concurrent_phone"}
    ev = {tid: sorted(rows, key=lambda e: e["seq"]) for tid, rows in _group(db["assignment_event"]).items()}

    def agent_on(aid: str, t: int) -> bool:
        return on_shift(shifts[agents[aid]["shift_id"]], t)

    # 1. Assignment history complete: seq 1..n with no gaps, REOPEN only after RESOLVE.
    history_broken = set()
    for tid, evs in ev.items():
        seqs = [e["seq"] for e in evs]
        types = [e["event_type"] for e in evs]
        if seqs != list(range(1, len(seqs) + 1)):
            history_broken.add(tid)
            flag("REOPEN_HISTORY_LOST", tid, "history_complete", f"assignment seq is {seqs[:5]}, not 1..n")
        elif "REOPEN" in types and "RESOLVE" not in types[:types.index("REOPEN")]:
            history_broken.add(tid)
            flag("REOPEN_HISTORY_LOST", tid, "history_complete", "REOPEN without an earlier RESOLVE")

    # 2. Lifecycle transitions (only meaningful when the history is complete).
    for tid, evs in ev.items():
        if tid in history_broken:
            continue
        state = "QUEUED"
        for e in evs:
            allowed, nxt = TRANSITIONS[e["event_type"]]
            if state not in allowed:
                flag("LIFECYCLE_INVALID", tid, "lifecycle", f"{e['event_type']} from {state}")
                break
            state = nxt

    # 3. Transfer loop: a transfer sends the ticket back to a queue it already left.
    for tid, evs in ev.items():
        path = []
        for e in evs:
            if e["event_type"] == "ASSIGN" and not path:
                path.append(e["queue_id"])
            elif e["event_type"] == "TRANSFER":
                if e["queue_id"] in path:
                    flag("TRANSFER_LOOP", tid, "transfer_loop", f"queue path {path + [e['queue_id']]}")
                    break
                path.append(e["queue_id"])

    # 4. Routing eligibility at each ASSIGN: on shift, has the queue skill, language rule.
    on_shift_by_skill: dict[tuple[str, int], list[str]] = {}
    for tid, evs in ev.items():
        tk = tickets[tid]
        for e in evs:
            if e["event_type"] != "ASSIGN":
                continue
            aid, t, skill = e["agent_id"], from_iso(e["ts"]), queue_skill[e["queue_id"]]
            if not agent_on(aid, t):
                flag("ROUTING_INELIGIBLE", tid, "routing_shift", f"{aid} off shift at {e['ts']}")
            if skill not in skills[aid]:
                flag("ROUTING_INELIGIBLE", tid, "routing_skill", f"{aid} lacks {skill}")
            speaks = tk["language_code"] in langs[aid]
            if e["translation_flag"] == 0 and not speaks:
                flag("ROUTING_INELIGIBLE", tid, "routing_language", f"{aid} does not speak {tk['language_code']}")
            if e["translation_flag"] == 1:
                key = (skill, t)
                if key not in on_shift_by_skill:
                    on_shift_by_skill[key] = [a for a in agents if skill in skills[a] and agent_on(a, t)]
                if any(tk["language_code"] in langs[a] for a in on_shift_by_skill[key]):
                    flag("ROUTING_INELIGIBLE", tid, "routing_language",
                         "translation used although an on-shift agent speaks the language")

    # 5. Capacity: sweep each agent's slots per channel; an ASSIGN that takes the
    #    agent above their limit is flagged. A slot is held from ASSIGN until the
    #    ticket's next event. Releases at minute t happen before assigns at t.
    marks: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
    for tid, evs in ev.items():
        ch = tickets[tid]["channel_id"]
        for i, e in enumerate(evs):
            if e["event_type"] == "ASSIGN":
                end = from_iso(evs[i + 1]["ts"]) if i + 1 < len(evs) else 10**9
                marks.setdefault((e["agent_id"], ch), []).extend([(from_iso(e["ts"]), 1, tid), (end, 0, tid)])
    for (aid, ch), ms in marks.items():
        load, limit = 0, agents[aid][limit_col[ch]]
        for _, kind, tid in sorted(ms):
            load += 1 if kind == 1 else -1
            if kind == 1 and load > limit:
                flag("CAPACITY_EXCEEDED", tid, "capacity", f"{aid} holds {load} {ch} tickets, limit {limit}")

    # 6. Priority: the safety rule first, then the full priority rule set.
    from .arrivals import assign_priority
    tiers = {c["customer_id"]: c["tier"] for c in db["customer"]}
    for tk in db["ticket"]:
        if is_safety[tk["intent_id"]] and tk["priority"] != "P1":
            flag("PRIORITY_SAFETY_VIOLATION", tk["ticket_id"], "safety_rule",
                 f"safety intent {tk['intent_id']} has priority {tk['priority']}")
        elif assign_priority(tk["intent_id"], tk["urgency"], tiers[tk["customer_id"]])[0] != tk["priority"]:
            flag("PRIORITY_RULE_MISMATCH", tk["ticket_id"], "priority_rules", "priority differs from the rules")

    # 7. SLA due dates and outcomes recomputed on the channel calendar.
    sla_rows = _group(db["sla_event"])
    for s in db["sla"]:
        tid = s["ticket_id"]
        tk = tickets[tid]
        d = dues(tk["priority"], tk["channel_id"], from_iso(tk["created_at"]))
        stored = (from_iso(s["first_response_due_at"]), from_iso(s["resolution_due_at"]), from_iso(s["started_at"]))
        if stored != (d["first_response_due"], d["resolution_due"], d["started_at"]):
            flag("SLA_CALENDAR_IGNORED", tid, "sla_due_dates",
                 f"stored resolution due {s['resolution_due_at']}, calendar gives {d['resolution_due']}")
            continue
        for r in sla_rows.get(tid, []):
            if r["event_type"].endswith(("_MET", "_BREACHED")):
                met = from_iso(r["ts"]) <= from_iso(r["due_at"])
                if met != r["event_type"].endswith("_MET"):
                    flag("SLA_OUTCOME_MISMATCH", tid, "sla_outcome", f"{r['sla_event_id']} outcome wrong")

    # 8. Escalation timing: an ESCALATE happens exactly at 80% of the cycle's
    #    resolution target; a cycle without one resolves strictly before that point.
    for tid, evs in ev.items():
        if tid in history_broken:
            continue
        tk = tickets[tid]
        esc_at = dues(tk["priority"], tk["channel_id"], from_iso(tk["created_at"]))["escalate_at"]
        escalated = False
        for e in evs:
            t = from_iso(e["ts"])
            if e["event_type"] == "ESCALATE" and not escalated:
                if t != esc_at:
                    flag("ESCALATION_TIMING", tid, "escalation_timing", f"escalated at {e['ts']}, rule says {esc_at}")
                escalated = True
            elif e["event_type"] == "RESOLVE" and not escalated and t >= esc_at:
                flag("ESCALATION_TIMING", tid, "escalation_timing", "resolved after the escalation point")
            elif e["event_type"] == "REOPEN":
                esc_at = dues(tk["priority"], tk["channel_id"], t)["escalate_at"]
    return found


def score(findings: list[dict], ground_truth: list[dict]) -> list[dict]:
    """Per anomaly type: expected, found, missed and false positives."""
    want = {(g["issue_type"], g["ticket_id"]) for g in ground_truth}
    got = {(f["issue_type"], f["ticket_id"]) for f in findings if f["issue_type"] in ANOMALY_TYPES}
    rows = []
    for issue in C.ANOMALY_TYPES:
        w = {k for k in want if k[0] == issue}
        g = {k for k in got if k[0] == issue}
        rows.append({"issue_type": issue, "expected": len(w), "found": len(g & w),
                     "missed": len(w - g), "false_positive": len(g - w)})
    return rows
