"""ID formats. IDs are built only here so every file uses the same spelling.

Formats from the problem statement: TKT-2026-000001, MSG-<ticket-id>-001,
AGT-000001, ASN-<ticket-id>-001, SLA-<ticket-id>. Formats for the other
entities follow the same zero-padded pattern.
"""

from __future__ import annotations

import re


def ticket_id(n: int) -> str:
    return f"TKT-2026-{n:06d}"


def customer_id(n: int) -> str:
    return f"CUS-{n:06d}"


def agent_id(n: int) -> str:
    return f"AGT-{n:06d}"


def message_id(tkt: str, seq: int) -> str:
    return f"MSG-{tkt}-{seq:03d}"


def assignment_id(tkt: str, seq: int) -> str:
    return f"ASN-{tkt}-{seq:03d}"


def sla_id(tkt: str) -> str:
    return f"SLA-{tkt}"


def sla_event_id(tkt: str, seq: int) -> str:
    return f"SLA-{tkt}-{seq:03d}"


def resolution_id(tkt: str, cycle: int) -> str:
    return f"RES-{tkt}-{cycle:03d}"


def anomaly_id(n: int) -> str:
    return f"GT-{n:04d}"


_TKT = r"TKT-2026-\d{6}"

# One regex per ID column; the validator checks every row against these.
PATTERNS: dict[str, re.Pattern[str]] = {
    "ticket_id": re.compile(rf"^{_TKT}$"),
    "customer_id": re.compile(r"^CUS-\d{6}$"),
    "agent_id": re.compile(r"^AGT-\d{6}$"),
    "message_id": re.compile(rf"^MSG-{_TKT}-\d{{3}}$"),
    "asn_id": re.compile(rf"^ASN-{_TKT}-\d{{3}}$"),
    "sla_id": re.compile(rf"^SLA-{_TKT}$"),
    "sla_event_id": re.compile(rf"^SLA-{_TKT}-\d{{3}}$"),
    "resolution_id": re.compile(rf"^RES-{_TKT}-\d{{3}}$"),
}
