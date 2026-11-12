"""Every business rule and tuning number in one place.

The system administrator actor owns this file: changing a calendar, an SLA
target or a routing threshold is a one-line edit here. Nothing else in the
code hard-codes a business value.

Time model: integer minutes since 2026-01-01T00:00Z (UTC, no daylight saving).
Day index d = t // 1440. 2026-01-01 is a Thursday.
"""

from __future__ import annotations

SEED = 20261022

# ---------------------------------------------------------------------------
# Scale: starter and full come from the same generator; only these numbers
# change. Spike/outage days are day indices inside the horizon.
# ---------------------------------------------------------------------------
SCALES: dict[str, dict] = {
    "starter": {
        "tickets": 1_000,
        "messages": 3_333,
        "agents": 20,
        "customers": 400,
        "days": 14,
        "spike_days": [3, 9],
        "outage_days": [6],
        "anomalies_per_type": 5,
    },
    "full": {
        "tickets": 30_000,
        "messages": 100_000,
        "agents": 100,
        "customers": 8_000,
        "days": 90,
        "spike_days": [10, 24, 37, 51, 66, 80],
        "outage_days": [20, 58],
        "anomalies_per_type": 30,
    },
}

DAY = 1440  # minutes

# Public holidays as day indices (2026-01-01, 2026-01-19, 2026-02-16).
# Business-hours calendars are closed on these days.
HOLIDAYS = frozenset({0, 18, 46})

# ---------------------------------------------------------------------------
# Channels and their SLA calendars (weekday Mon=0 -> open segments, minutes
# within the day). P1 tickets ignore these and run on a 24x7 clock.
# ---------------------------------------------------------------------------
EMAIL_HOURS = {d: [(8 * 60, 18 * 60)] for d in range(5)}  # Mon-Fri 08-18
LIVE_HOURS = {d: [(7 * 60, 22 * 60)] for d in range(6)}   # Mon-Sat 07-22

CHANNELS: dict[str, dict] = {
    # share = fraction of arrivals; limit = max concurrent tickets per agent.
    # Calibrated (see README) so queues form at peaks and SLA attainment is not trivially 100%.
    "EMAIL": {"name": "Email", "hours": EMAIL_HOURS, "share": 0.45, "limit": 2},
    "CHAT": {"name": "Live chat", "hours": LIVE_HOURS, "share": 0.35, "limit": 2},
    "PHONE": {"name": "Phone", "hours": LIVE_HOURS, "share": 0.20, "limit": 1},
}

# ISO 639-1 codes. share = customer preferred-language mix.
LANGUAGES: dict[str, dict] = {
    "en": {"name": "English", "share": 0.70},
    "es": {"name": "Spanish", "share": 0.15},
    "fr": {"name": "French", "share": 0.08},
    "de": {"name": "German", "share": 0.07},
}

SKILLS: dict[str, str] = {
    "SKL-BILLING": "Billing and refunds",
    "SKL-ACCOUNT": "Accounts and access",
    "SKL-TECH": "Technical support",
    "SKL-SALES": "Sales and prospects",
    "SKL-T2": "Tier-2 escalations",
}

# Each queue needs exactly one skill (Queue N:1 Skill).
QUEUES: dict[str, dict] = {
    "QUE-BILLING": {"name": "Billing", "skill": "SKL-BILLING"},
    "QUE-ACCOUNT": {"name": "Accounts", "skill": "SKL-ACCOUNT"},
    "QUE-TECH": {"name": "Technical", "skill": "SKL-TECH"},
    "QUE-SALES": {"name": "Sales", "skill": "SKL-SALES"},
    "QUE-T2": {"name": "Tier-2 escalations", "skill": "SKL-T2"},
}
ESCALATION_QUEUE = "QUE-T2"

# ---------------------------------------------------------------------------
# Intent taxonomy. is_safety intents must always be P1 (the safety rule).
# weight = share of arrivals outside outage windows.
# ---------------------------------------------------------------------------
INTENTS: dict[str, dict] = {
    "INT-BILLING_DISPUTE": {"queue": "QUE-BILLING", "priority": "P3", "is_safety": False, "weight": 0.18},
    "INT-REFUND": {"queue": "QUE-BILLING", "priority": "P3", "is_safety": False, "weight": 0.10},
    "INT-PASSWORD_RESET": {"queue": "QUE-ACCOUNT", "priority": "P4", "is_safety": False, "weight": 0.14},
    "INT-ACCOUNT_CHANGE": {"queue": "QUE-ACCOUNT", "priority": "P4", "is_safety": False, "weight": 0.08},
    "INT-GENERAL_QUESTION": {"queue": "QUE-ACCOUNT", "priority": "P4", "is_safety": False, "weight": 0.10},
    "INT-TECH_ISSUE": {"queue": "QUE-TECH", "priority": "P3", "is_safety": False, "weight": 0.20},
    "INT-OUTAGE": {"queue": "QUE-TECH", "priority": "P1", "is_safety": True, "weight": 0.03},
    "INT-SECURITY": {"queue": "QUE-ACCOUNT", "priority": "P1", "is_safety": True, "weight": 0.02},
    "INT-SAFETY_HAZARD": {"queue": "QUE-TECH", "priority": "P1", "is_safety": True, "weight": 0.01},
    "INT-SALES_INQUIRY": {"queue": "QUE-SALES", "priority": "P4", "is_safety": False, "weight": 0.10},
    "INT-DEMO_REQUEST": {"queue": "QUE-SALES", "priority": "P4", "is_safety": False, "weight": 0.04},
}
PRIORITIES = ["P1", "P2", "P3", "P4"]  # P1 = most urgent

# Priority rules, applied in order by arrivals.assign_priority(). Each ticket
# records the id of the last rule that changed its priority.
PRIORITY_RULES: list[dict] = [
    {"rule_id": "PRL-001", "description": "Start from the intent's default priority", "effective_from": 0},
    {"rule_id": "PRL-002", "description": "Urgency HIGH raises priority one level", "effective_from": 0},
    {"rule_id": "PRL-003", "description": "ENTERPRISE customers raise priority one level", "effective_from": 0},
    {"rule_id": "PRL-004", "description": "Non-safety tickets are capped at P2", "effective_from": 0},
    {"rule_id": "PRL-005", "description": "SAFETY RULE: safety intents are always P1", "effective_from": 0},
]

URGENCY_SHARE = {"LOW": 0.35, "MEDIUM": 0.50, "HIGH": 0.15}
CUSTOMER_TIER_SHARE = {"STANDARD": 0.70, "PREMIUM": 0.22, "ENTERPRISE": 0.08}
PROSPECT_SHARE = 0.12  # customers with no account (marketing/sales leads)

# ---------------------------------------------------------------------------
# SLA targets in business minutes: (first response, resolution).
# P1 runs on the 24x7 clock; P2-P4 on the channel calendar.
# ---------------------------------------------------------------------------
SLA_TARGETS: dict[tuple[str, str], tuple[int, int]] = {
    ("P1", "EMAIL"): (30, 480), ("P1", "CHAT"): (5, 480), ("P1", "PHONE"): (5, 480),
    ("P2", "EMAIL"): (60, 600), ("P2", "CHAT"): (10, 600), ("P2", "PHONE"): (10, 600),
    ("P3", "EMAIL"): (240, 1200), ("P3", "CHAT"): (30, 1200), ("P3", "PHONE"): (20, 1200),
    ("P4", "EMAIL"): (480, 3000), ("P4", "CHAT"): (60, 3000), ("P4", "PHONE"): (30, 3000),
}
ESCALATE_AT_FRACTION = 0.8  # escalate when 80% of the resolution target is used

# ---------------------------------------------------------------------------
# Agents: shifts, skills, languages. Shifts ignore holidays (the centre is
# staffed; only the SLA calendar pauses).
# ---------------------------------------------------------------------------
SHIFTS: dict[str, dict] = {
    # start/end in minutes within the day; NIGHT wraps past midnight
    "SHF-DAY": {"start": 7 * 60, "end": 15 * 60, "weekdays": [0, 1, 2, 3, 4, 5], "share": 0.50},
    "SHF-EVE": {"start": 14 * 60, "end": 22 * 60, "weekdays": [0, 1, 2, 3, 4, 5], "share": 0.35},
    "SHF-NIGHT": {"start": 22 * 60, "end": 7 * 60, "weekdays": [0, 1, 2, 3, 4, 5, 6], "share": 0.15},
}
FRONTLINE_SKILLS = ["SKL-BILLING", "SKL-ACCOUNT", "SKL-TECH"]
SALES_AGENT_SHARE = 0.12
T2_AGENT_SHARE = 0.15
SECOND_LANGUAGE_SHARE = 0.45  # agents speaking a non-English language too

# ---------------------------------------------------------------------------
# Arrivals: hour-of-day and weekday weights, spikes, outages.
# ---------------------------------------------------------------------------
HOUR_WEIGHTS = [  # 00..23 UTC
    0.3, 0.2, 0.2, 0.2, 0.3, 0.5, 0.8, 1.2, 1.8, 2.2, 2.4, 2.4,
    2.2, 2.3, 2.4, 2.2, 2.0, 1.7, 1.4, 1.1, 0.9, 0.7, 0.5, 0.4,
]
WEEKDAY_WEIGHTS = [1.15, 1.10, 1.05, 1.05, 1.00, 0.55, 0.40]  # Mon..Sun
SPIKE_HOURS = (9, 13)        # spike window on spike days, [start, end) hour
SPIKE_MULTIPLIER = 4.0
OUTAGE_HOURS = (14, 17)      # outage window on outage days
OUTAGE_MULTIPLIER = 6.0
OUTAGE_INTENT_SHARE = 0.6    # share of outage-window arrivals that are INT-OUTAGE

# ---------------------------------------------------------------------------
# Handling and lifecycle behaviour (drawn per ticket before routing).
# ---------------------------------------------------------------------------
HANDLE_MEDIAN_MIN = {"EMAIL": 300, "CHAT": 35, "PHONE": 20}  # minutes a slot is held (active work, incl. waiting on internal teams)
HANDLE_SIGMA = 0.8           # lognormal spread
T2_HANDLE_FACTOR = 1.5
FIRST_RESPONSE_FRACTION = 0.25  # first agent reply lands 25% into handling
MISROUTE_PROB = 0.08         # triage sends the ticket to the wrong queue
REOPEN_BASE_PROB = 0.05
REOPEN_IF_BREACHED = 0.10    # added when the resolution SLA was breached
REOPEN_IF_TRANSFERRED = 0.05
REOPEN_DELAY_MIN = (60, 2 * DAY)  # uniform range after resolution
RETRY_TICK_MIN = 5           # waiting tickets re-check for agents this often

# CSAT (1..5) = 5 - 1.5*breached - 0.5*transfers - 1*reopened - wait_penalty + noise
CSAT_RESPONSE_RATE = 0.35
CSAT_WAIT_PENALTY_PER_HOUR = 0.25  # capped at 1.5
CSAT_NOISE = [-1, 0, 0, 0, 1]

# ---------------------------------------------------------------------------
# Message threading: extra messages beyond the first customer message and the
# first agent reply, per channel (uniform integer range).
# ---------------------------------------------------------------------------
EXTRA_MESSAGES = {"EMAIL": (0, 3), "CHAT": (1, 6), "PHONE": (0, 1)}
MAX_MESSAGES_PER_TICKET = 999

# Anomaly types injected after the clean baseline.
ANOMALY_TYPES = [
    "CAPACITY_EXCEEDED",
    "SLA_CALENDAR_IGNORED",
    "REOPEN_HISTORY_LOST",
    "TRANSFER_LOOP",
    "PRIORITY_SAFETY_VIOLATION",
]
