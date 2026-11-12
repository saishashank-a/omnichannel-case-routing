"""Master and reference data, generated first so later tables can point at it.

Each table is a plain list of dicts (one dict per row), keyed by table name.
"""

from __future__ import annotations

import random

from . import config as C
from . import ids
from .bizhours import to_iso

Tables = dict[str, list[dict]]

FIRST_NAMES = ["Asha", "Ben", "Carla", "Dev", "Elena", "Farid", "Grace", "Hiro", "Ines", "Jonas",
               "Kavya", "Liam", "Mara", "Nikhil", "Olga", "Pedro", "Quinn", "Rosa", "Sven", "Tara"]
LAST_NAMES = ["Alvarez", "Brooks", "Chen", "Dubois", "Eriksen", "Fischer", "Gupta", "Haddad", "Ito",
              "Jensen", "Kumar", "Lopez", "Moreau", "Novak", "Okafor", "Patel", "Rossi", "Schmidt"]

# Frontline skill pairs rotated within each shift, so any shift with 2+ agents
# covers all three frontline skills.
SKILL_PAIRS = [("SKL-BILLING", "SKL-ACCOUNT"), ("SKL-ACCOUNT", "SKL-TECH"), ("SKL-TECH", "SKL-BILLING")]
OTHER_LANGUAGES = ["es", "fr", "de"]


def build_reference() -> Tables:
    """Lookup tables copied straight from config, so the data documents its own rules."""
    return {
        "channel": [{"channel_id": c, "name": v["name"], "default_max_concurrent": v["limit"]}
                    for c, v in C.CHANNELS.items()],
        "language": [{"language_code": k, "name": v["name"]} for k, v in C.LANGUAGES.items()],
        "skill": [{"skill_id": k, "name": v} for k, v in C.SKILLS.items()],
        "queue": [{"queue_id": k, "name": v["name"], "skill_id": v["skill"]} for k, v in C.QUEUES.items()],
        "intent": [{"intent_id": k, "queue_id": v["queue"], "default_priority": v["priority"],
                    "is_safety": int(v["is_safety"])} for k, v in C.INTENTS.items()],
        "priority_rule": [{"rule_id": r["rule_id"], "description": r["description"],
                           "effective_from": to_iso(r["effective_from"]), "effective_to": None}
                          for r in C.PRIORITY_RULES],
        "sla_policy": [{"priority": p, "channel_id": ch, "first_response_min": fr, "resolution_min": res,
                        "calendar": "24x7" if p == "P1" else "CHANNEL"}
                       for (p, ch), (fr, res) in C.SLA_TARGETS.items()],
        "shift": [{"shift_id": k, "start_min": v["start"], "end_min": v["end"],
                   "weekdays": ",".join(str(d) for d in v["weekdays"])} for k, v in C.SHIFTS.items()],
    }


def _name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _weighted(rng: random.Random, shares: dict[str, float]) -> str:
    keys = list(shares)
    return rng.choices(keys, weights=[shares[k] for k in keys], k=1)[0]


def build_customers(rng: random.Random, n: int) -> list[dict]:
    """Customers and prospects. Prospects have no account, so no tier."""
    rows = []
    for i in range(1, n + 1):
        is_prospect = rng.random() < C.PROSPECT_SHARE
        rows.append({
            "customer_id": ids.customer_id(i),
            "display_name": _name(rng),
            "customer_type": "PROSPECT" if is_prospect else "CUSTOMER",
            "tier": None if is_prospect else _weighted(rng, C.CUSTOMER_TIER_SHARE),
            "preferred_language": _weighted(rng, {k: v["share"] for k, v in C.LANGUAGES.items()}),
            # account opened some time in the year before the horizon (effective date)
            "created_at": to_iso(-rng.randint(1, 365) * C.DAY),
        })
    return rows


def _shift_counts(n: int) -> dict[str, int]:
    """Agents per shift by config share; remainder goes to the day shift."""
    counts = {s: max(3, round(n * v["share"])) for s, v in C.SHIFTS.items() if s != "SHF-DAY"}
    counts["SHF-DAY"] = n - sum(counts.values())
    return {s: counts[s] for s in C.SHIFTS}  # keep config order


def build_agents(rng: random.Random, n: int) -> Tables:
    """Agents plus their skill and language bridge rows.

    Coverage is guaranteed by construction, not by luck: within each shift,
    agent k gets frontline skill pair k%3, a second language
    OTHER_LANGUAGES[k%3] when k<3, Tier-2 when k==0, Sales when k==1.
    Every agent speaks English. Further skills/languages are random extras.
    """
    agents, agent_skill, agent_language = [], [], []
    num = 0
    for shift_id, count in _shift_counts(n).items():
        for k in range(count):
            num += 1
            aid = ids.agent_id(num)
            hired = to_iso(-rng.randint(30, 3 * 365) * C.DAY)
            agents.append({
                "agent_id": aid,
                "display_name": _name(rng),
                "shift_id": shift_id,
                "max_concurrent_email": C.CHANNELS["EMAIL"]["limit"],
                "max_concurrent_chat": C.CHANNELS["CHAT"]["limit"],
                "max_concurrent_phone": C.CHANNELS["PHONE"]["limit"],
                "hired_at": hired,
                "status": "ACTIVE",
            })
            skills = list(SKILL_PAIRS[k % 3])
            if k == 0 or rng.random() < C.T2_AGENT_SHARE:
                skills.append("SKL-T2")
            if k == 1 or rng.random() < C.SALES_AGENT_SHARE:
                skills.append("SKL-SALES")
            langs = ["en"]
            if k < 3:
                langs.append(OTHER_LANGUAGES[k])
            elif rng.random() < C.SECOND_LANGUAGE_SHARE:
                langs.append(rng.choice(OTHER_LANGUAGES))
            agent_skill += [{"agent_id": aid, "skill_id": s, "effective_from": hired} for s in sorted(skills)]
            agent_language += [{"agent_id": aid, "language_code": lg, "effective_from": hired}
                               for lg in sorted(langs)]
    return {"agent": agents, "agent_skill": agent_skill, "agent_language": agent_language}


def build_master(seed: int, scale: dict) -> Tables:
    """All master data. Each stage gets its own RNG so adding draws in one
    stage never shifts the random numbers of another."""
    tables = build_reference()
    tables["customer"] = build_customers(random.Random(f"{seed}:customers"), scale["customers"])
    tables |= build_agents(random.Random(f"{seed}:agents"), scale["agents"])
    return tables
