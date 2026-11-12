"""Inject the five labelled anomaly types into a clean baseline.

Rules every injector follows:
- Targets are drawn from a filtered candidate list sorted by ticket_id, with
  their own RNG, and each ticket is used by at most one anomaly.
- Only the target ticket's rows change. Its derived columns are recomputed
  from its (now faulty) events, so the only thing wrong is the injected fault,
  and the checker should flag exactly that ticket under exactly that type.
- Every injection writes one ground-truth row. Ground truth goes to its own
  folder and never into the input tables.
"""

from __future__ import annotations

import random

from . import config as C
from . import ids
from .bizhours import to_iso
from .outcomes import derive_ticket_columns
from .routing import on_shift
from .sla import build_sla, dues

Tables = dict[str, list[dict]]


def expected_decisions(tables: Tables) -> list[dict]:
    """The rule-based decisions for every ticket, captured before injection."""
    rows = []
    for tk in tables["ticket"]:
        d = dues(tk["priority"], tk["channel_id"], tk["created_at"])
        rows.append({"ticket_id": tk["ticket_id"], "expected_priority": tk["priority"],
                     "expected_queue_id": C.INTENTS[tk["intent_id"]]["queue"],
                     "expected_first_response_due_at": to_iso(d["first_response_due"]),
                     "expected_resolution_due_at": to_iso(d["resolution_due"]),
                     "expected_escalate_at": to_iso(d["escalate_at"])})
    return rows


class Injector:
    def __init__(self, tables: Tables, seed: int):
        self.t = tables
        self.rng = random.Random(f"{seed}:anomalies")
        self.used: set[str] = set()
        self.gt: list[dict] = []
        self.tickets = {tk["ticket_id"]: tk for tk in tables["ticket"]}

    # ---- helpers ----------------------------------------------------------
    def events(self, tid: str) -> list[dict]:
        return [e for e in self.t["assignment_event"] if e["ticket_id"] == tid]

    def pick(self, candidates: list[str], n: int) -> list[str]:
        pool = sorted(c for c in candidates if c not in self.used)
        self.rng.shuffle(pool)
        return pool[:n]

    def replace_rows(self, table: str, tid: str, new_rows: list[dict]) -> None:
        """Swap one ticket's rows in a table, keeping the others untouched."""
        self.t[table] = [r for r in self.t[table] if r["ticket_id"] != tid] + new_rows

    def refresh(self, tid: str) -> None:
        """Recompute the ticket's snapshot columns and SLA rows from its events."""
        tk = self.tickets[tid]
        msgs = [m for m in self.t["message"] if m["ticket_id"] == tid]
        derive_ticket_columns([tk], self.events(tid), msgs)
        header, rows = build_sla([tk], self.events(tid))
        self.replace_rows("sla", tid, header)
        self.replace_rows("sla_event", tid, rows)

    def label(self, issue: str, tid: str, table: str, entity: str, rule: str, field: str,
              injected: object, expected: object) -> None:
        self.used.add(tid)
        self.gt.append({"anomaly_id": ids.anomaly_id(len(self.gt) + 1), "issue_type": issue, "ticket_id": tid,
                        "entity_table": table, "entity_id": entity, "rule_violated": rule, "field": field,
                        "injected_value": str(injected), "expected_value": str(expected)})

    # ---- the five anomaly types ----------------------------------------------
    def priority_safety(self, n: int) -> None:
        cands = [tk["ticket_id"] for tk in self.t["ticket"] if C.INTENTS[tk["intent_id"]]["is_safety"]
                 and tk["escalation_count"] == 0 and tk["reopen_count"] == 0]
        for tid in self.pick(cands, n):
            self.tickets[tid]["priority"] = "P3"
            self.refresh(tid)  # SLA rows now follow the wrong priority, consistently
            self.label("PRIORITY_SAFETY_VIOLATION", tid, "ticket", tid, "PRL-005: safety intents are always P1",
                       "priority", "P3", "P1")

    def sla_calendar(self, n: int) -> None:
        cands = []
        for tk in self.t["ticket"]:
            if tk["priority"] == "P1" or tk["reopen_count"] or tk["escalation_count"]:
                continue
            d = dues(tk["priority"], tk["channel_id"], tk["created_at"])
            if d["resolution_due"] != tk["created_at"] + C.SLA_TARGETS[(tk["priority"], tk["channel_id"])][1]:
                cands.append(tk["ticket_id"])
        for tid in self.pick(cands, n):
            tk = self.tickets[tid]
            fr, res = C.SLA_TARGETS[(tk["priority"], tk["channel_id"])]
            start = tk["created_at"]                  # the fault: wall-clock minutes, calendar ignored
            header = [s for s in self.t["sla"] if s["ticket_id"] == tid][0]
            right = header["resolution_due_at"]
            header |= {"started_at": start, "first_response_due_at": start + fr, "resolution_due_at": start + res}
            rows = []
            for r in sorted((r for r in self.t["sla_event"] if r["ticket_id"] == tid), key=lambda r: r["sla_event_id"]):
                r = dict(r)
                if r["event_type"] == "CLOCK_STARTED":
                    r["ts"], r["due_at"] = start, start + res
                elif r["event_type"].startswith("FIRST_RESPONSE"):
                    r["due_at"] = start + fr
                    r["event_type"] = "FIRST_RESPONSE_" + ("MET" if r["ts"] <= r["due_at"] else "BREACHED")
                elif r["event_type"].startswith("RESOLUTION"):
                    r["due_at"] = start + res
                    r["event_type"] = "RESOLUTION_" + ("MET" if r["ts"] <= r["due_at"] else "BREACHED")
                rows.append(r)
            rows.sort(key=lambda r: r["ts"])
            for seq, r in enumerate(rows, start=1):
                r["sla_event_id"] = ids.sla_event_id(tid, seq)
            self.replace_rows("sla_event", tid, rows)
            self.label("SLA_CALENDAR_IGNORED", tid, "sla", ids.sla_id(tid),
                       f"SLA for {tk['priority']} {tk['channel_id']} must use the channel calendar",
                       "resolution_due_at", to_iso(start + res), to_iso(right))

    def reopen_history(self, n: int) -> None:
        cands = [tk["ticket_id"] for tk in self.t["ticket"]
                 if tk["reopen_count"] == 1 and tk["escalation_count"] == 0 and tk["transfer_count"] == 0]
        for tid in self.pick(cands, n):
            evs = self.events(tid)
            reopen_seq = next(e["seq"] for e in evs if e["event_type"] == "REOPEN")
            lost = [e for e in evs if e["seq"] < reopen_seq]
            self.replace_rows("assignment_event", tid, [e for e in evs if e["seq"] >= reopen_seq])
            self.t["resolution"] = [r for r in self.t["resolution"] if not (r["ticket_id"] == tid and r["cycle_no"] == 1)]
            self.refresh(tid)
            self.label("REOPEN_HISTORY_LOST", tid, "assignment_event", lost[0]["asn_id"],
                       "reopened tickets keep their full assignment history", "rows",
                       f"{len(lost)} pre-reopen events deleted", f"{len(lost)} events present")

    def transfer_loop(self, n: int) -> None:
        cands = [tk["ticket_id"] for tk in self.t["ticket"]
                 if tk["transfer_count"] == 1 and tk["escalation_count"] == 0 and tk["reopen_count"] == 0]
        for tid in self.pick(cands, n):
            evs = self.events(tid)
            i = next(k for k, e in enumerate(evs) if e["event_type"] == "TRANSFER")
            home, wrong = evs[i]["queue_id"], evs[i - 1]["queue_id"]
            ts = evs[i]["ts"]
            bounce = [
                {**evs[i], "queue_id": wrong, "reason": f"sent back to {wrong} by mistake"},
                {**evs[i], "queue_id": home, "reason": f"returned to {home}"},
            ]
            new = evs[: i + 1] + bounce + evs[i + 1:]
            for seq, e in enumerate(new, start=1):          # renumber this ticket's history
                e["seq"], e["asn_id"] = seq, ids.assignment_id(tid, seq)
            self.replace_rows("assignment_event", tid, new)
            self.refresh(tid)
            self.label("TRANSFER_LOOP", tid, "assignment_event", new[i + 1]["asn_id"],
                       "a ticket must not be transferred back to a queue it already left", "queue_id",
                       f"{wrong} -> {home} -> {wrong} -> {home} at {to_iso(ts)}", f"{wrong} -> {home}")

    def capacity(self, n: int) -> None:
        """Hand a simple ASSIGN->RESOLVE ticket to an eligible agent who is already full."""
        agents = {a["agent_id"]: a for a in self.t["agent"]}
        skills, langs = {}, {}
        for r in self.t["agent_skill"]:
            skills.setdefault(r["agent_id"], set()).add(r["skill_id"])
        for r in self.t["agent_language"]:
            langs.setdefault(r["agent_id"], set()).add(r["language_code"])
        limit_col = {"EMAIL": "max_concurrent_email", "CHAT": "max_concurrent_chat", "PHONE": "max_concurrent_phone"}

        by_tkt: dict[str, list[dict]] = {}
        for e in sorted(self.t["assignment_event"], key=lambda e: (e["ticket_id"], e["seq"])):
            by_tkt.setdefault(e["ticket_id"], []).append(e)
        slots: dict[tuple[str, str], list[tuple[int, int]]] = {}   # (agent, channel) -> [(start, end))
        for tid, evs in by_tkt.items():
            ch = self.tickets[tid]["channel_id"]
            for k, e in enumerate(evs):
                if e["event_type"] == "ASSIGN":
                    end = evs[k + 1]["ts"] if k + 1 < len(evs) else 10**9
                    slots.setdefault((e["agent_id"], ch), []).append((e["ts"], end))

        cands = [tid for tid, evs in by_tkt.items() if [e["event_type"] for e in evs] == ["ASSIGN", "RESOLVE"]]
        done, targets = 0, set()   # agents already overloaded on purpose
        for tid in self.pick(cands, len(cands)):
            if done == n:
                break
            tk, (a_ev, r_ev) = self.tickets[tid], by_tkt[tid]
            ch, a, r = tk["channel_id"], a_ev["ts"], r_ev["ts"]
            if a_ev["agent_id"] in targets:
                continue  # moving work off an overloaded agent could hide their injected overload
            skill = C.QUEUES[a_ev["queue_id"]]["skill"]
            for bid in sorted(agents):
                busy = slots.get((bid, ch), [])
                ok = (bid != a_ev["agent_id"] and skill in skills[bid]
                      and on_shift(C.SHIFTS[agents[bid]["shift_id"]], a)
                      and (tk["language_code"] in langs[bid]) == (a_ev["translation_flag"] == 0)
                      and sum(s < a < e for s, e in busy) == agents[bid][limit_col[ch]]   # already full
                      and not any(a <= s < r for s, _ in busy))                            # no new work meanwhile
                if not ok:
                    continue
                old = a_ev["agent_id"]
                a_ev["agent_id"] = r_ev["agent_id"] = bid
                slots[(old, ch)].remove((a, r))                  # keep the busy map current
                slots.setdefault((bid, ch), []).append((a, r))
                for m in self.t["message"]:
                    if m["ticket_id"] == tid and m["agent_id"] == old:
                        m["agent_id"] = bid
                for res in self.t["resolution"]:
                    if res["ticket_id"] == tid:
                        res["agent_id"] = bid
                self.label("CAPACITY_EXCEEDED", tid, "assignment_event", a_ev["asn_id"],
                           f"agent {ch} concurrency limit is {agents[bid][limit_col[ch]]}", "agent_id", bid, old)
                targets.add(bid)
                done += 1
                break


def inject(tables: Tables, seed: int, per_type: int) -> list[dict]:
    """Mutates `tables` in place and returns the ground-truth rows.

    Capacity runs last because other injectors delete or add events, which
    changes who is busy when.
    """
    inj = Injector(tables, seed)
    inj.priority_safety(per_type)
    inj.sla_calendar(per_type)
    inj.reopen_history(per_type)
    inj.transfer_loop(per_type)
    inj.capacity(per_type)
    for table in ("assignment_event", "sla", "sla_event", "resolution"):
        tables[table].sort(key=lambda r: next(iter(r.values())))  # back to primary-key order
    return inj.gt
