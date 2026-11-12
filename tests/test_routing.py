"""Routing rules on tiny hand-built scenarios: skill, language, capacity, shift, escalation."""

from caserouting import config as C
from caserouting.routing import next_shift_start, on_shift, simulate
from caserouting.sla import dues

MON_10 = 4 * C.DAY + 10 * 60   # day 4 = Mon 2026-01-05, 10:00 UTC (day shift, chat open)


def agent(n: int, shift: str = "SHF-DAY", chat: int = 3) -> dict:
    return {"agent_id": f"AGT-{n:06d}", "shift_id": shift, "max_concurrent_email": 5,
            "max_concurrent_chat": chat, "max_concurrent_phone": 1}


def master(agents: list[dict], skills: dict[int, list[str]], langs: dict[int, list[str]]) -> dict:
    return {
        "agent": agents,
        "agent_skill": [{"agent_id": f"AGT-{n:06d}", "skill_id": s} for n, ss in skills.items() for s in ss],
        "agent_language": [{"agent_id": f"AGT-{n:06d}", "language_code": l} for n, ls in langs.items() for l in ls],
    }


def ticket(n: int, t: int, lang: str = "en", intent: str = "INT-BILLING_DISPUTE", prio: str = "P3") -> dict:
    return {"ticket_id": f"TKT-2026-{n:06d}", "channel_id": "CHAT", "intent_id": intent,
            "language_code": lang, "priority": prio, "created_at": t}


def draw(handle: int = 30, misroute: bool = False) -> dict:
    return {"handle": [handle, handle], "t2_handle": handle, "misroute": misroute, "wrong_queue": "QUE-TECH",
            "discover_frac": 0.5, "reopen_u": 1.0, "reopen_delay": 60, "resolution_code": "SOLVED"}


def run(tickets: list[dict], draws: list[dict], m: dict) -> list[dict]:
    d = {tk["ticket_id"]: dr for tk, dr in zip(tickets, draws)}
    return simulate(tickets, d, m, 90 * C.DAY)["assignment_event"]


def assigns(events: list[dict]) -> list[dict]:
    return [e for e in events if e["event_type"] == "ASSIGN"]


def test_skill_is_required():
    m = master([agent(1), agent(2)], {1: ["SKL-TECH"], 2: ["SKL-BILLING"]}, {1: ["en"], 2: ["en"]})
    ev = run([ticket(1, MON_10)], [draw()], m)
    assert assigns(ev)[0]["agent_id"] == "AGT-000002"


def test_language_match_preferred_then_translation_fallback():
    m = master([agent(1), agent(2)], {1: ["SKL-BILLING"], 2: ["SKL-BILLING"]}, {1: ["en"], 2: ["en", "es"]})
    ev = run([ticket(1, MON_10, lang="es"), ticket(2, MON_10 + 1, lang="fr")], [draw(), draw()], m)
    a = {e["ticket_id"]: e for e in assigns(ev)}
    assert a["TKT-2026-000001"]["agent_id"] == "AGT-000002"
    assert a["TKT-2026-000001"]["translation_flag"] == 0
    assert a["TKT-2026-000002"]["translation_flag"] == 1   # nobody speaks fr


def test_capacity_limit_makes_ticket_wait():
    m = master([agent(1, chat=1)], {1: ["SKL-BILLING"]}, {1: ["en"]})
    ev = run([ticket(1, MON_10), ticket(2, MON_10)], [draw(handle=30), draw(handle=30)], m)
    a = {e["ticket_id"]: e["ts"] for e in assigns(ev)}
    assert a["TKT-2026-000001"] == MON_10
    assert a["TKT-2026-000002"] == MON_10 + 30   # slot freed at exactly +30


def test_off_shift_ticket_waits_for_shift_start():
    m = master([agent(1)], {1: ["SKL-BILLING"]}, {1: ["en"]})
    night = 4 * C.DAY + 2 * 60   # Monday 02:00, day shift starts 07:00
    ev = run([ticket(1, night)], [draw()], m)
    assert assigns(ev)[0]["ts"] == 4 * C.DAY + 7 * 60


def test_misroute_transfers_to_home_queue():
    m = master([agent(1), agent(2)], {1: ["SKL-TECH"], 2: ["SKL-BILLING"]}, {1: ["en"], 2: ["en"]})
    ev = run([ticket(1, MON_10)], [draw(handle=40, misroute=True)], m)
    assert [e["event_type"] for e in ev] == ["ASSIGN", "TRANSFER", "ASSIGN", "RESOLVE"]
    assert ev[0]["queue_id"] == "QUE-TECH" and ev[1]["queue_id"] == "QUE-BILLING"
    assert ev[1]["ts"] == MON_10 + 20       # discovered halfway through handling


def test_escalation_fires_exactly_at_80_percent():
    m = master([agent(1), agent(2)], {1: ["SKL-BILLING"], 2: ["SKL-T2"]}, {1: ["en"], 2: ["en"]})
    tk = ticket(1, MON_10)
    esc_at = dues("P3", "CHAT", MON_10)["escalate_at"]
    ev = run([tk], [draw(handle=10_000)], m)       # work far longer than the SLA allows
    esc = [e for e in ev if e["event_type"] == "ESCALATE"]
    assert len(esc) == 1 and esc[0]["ts"] == esc_at and esc[0]["queue_id"] == "QUE-T2"


def test_night_shift_wraps_midnight():
    night = C.SHIFTS["SHF-NIGHT"]
    assert on_shift(night, 4 * C.DAY + 23 * 60)          # Mon 23:00
    assert on_shift(night, 5 * C.DAY + 3 * 60)           # Tue 03:00 (Monday's shift)
    assert not on_shift(night, 5 * C.DAY + 12 * 60)      # Tue 12:00
    day = C.SHIFTS["SHF-DAY"]
    assert next_shift_start(day, 4 * C.DAY + 16 * 60) == 5 * C.DAY + 7 * 60
