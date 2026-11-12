"""The generation pipeline, in dependency order (parents before children)."""

from __future__ import annotations

from pathlib import Path

from . import config as C
from .arrivals import build_tickets
from .export import write_dataset, write_manifest
from .master import build_master
from .messages import build_messages
from .outcomes import apply_csat, derive_ticket_columns
from .routing import simulate
from .sla import build_sla


def build_baseline(seed: int, scale: dict) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Clean, rule-following dataset. Returns (tables, pre-drawn values)."""
    tables = build_master(seed, scale)                                      # 1. master data
    tickets, draws = build_tickets(seed, scale, tables["customer"])         # 2. arrivals
    sim = simulate(tickets, draws, tables, scale["days"] * C.DAY)           # 3. routing
    events = sim["assignment_event"]
    messages = build_messages(tickets, events, sim["first_response"], draws, scale["messages"])  # 4.
    derive_ticket_columns(tickets, events, messages)                       # 5. snapshot columns
    sla_headers, sla_events = build_sla(tickets, events)                    # 6. SLA records
    apply_csat(tickets, events, sla_events, sim["resolution"], draws)       # 7. CSAT
    tables |= {"ticket": tickets, "sla": sla_headers, "assignment_event": events,
               "sla_event": sla_events, "message": messages, "resolution": sim["resolution"]}
    return tables, draws


def generate(scale_name: str, seed: int, out: Path) -> dict:
    scale = C.SCALES[scale_name]
    tables, _ = build_baseline(seed, scale)
    out.mkdir(parents=True, exist_ok=True)
    write_dataset(out, tables)
    info = {"generator": "python -m caserouting generate", "scale": scale_name, "seed": seed,
            "parameters": scale, "external_data": "none (fully synthetic)"}
    return write_manifest(out, info)
