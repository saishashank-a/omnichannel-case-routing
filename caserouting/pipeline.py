"""The generation pipeline, in dependency order (parents before children).

generate():
  1. build a clean baseline (master -> arrivals -> routing -> messages -> SLA -> CSAT)
  2. validate the baseline in memory: it must have 0 findings
  3. snapshot the expected rule-based decisions
  4. inject labelled anomalies into the baseline
  5. export CSV / JSON / SQL, ground truth (in its own folder)
  6. re-load the exported files and validate them from scratch
  7. write findings, metrics, validation summary and the checksum manifest
"""

from __future__ import annotations

from pathlib import Path

from . import config as C
from .anomalies import expected_decisions, inject
from .arrivals import build_tickets
from .export import to_export_rows, write_csv, write_dataset, write_json, write_manifest
from .master import build_master
from .messages import build_messages
from .outcomes import apply_csat, derive_ticket_columns
from .report import metrics, summary_markdown
from .routing import simulate
from .sla import build_sla
from .validate import business_checks, load_dir, score, structural_checks

GT_COLUMNS = ["anomaly_id", "issue_type", "ticket_id", "entity_table", "entity_id", "rule_violated", "field",
              "injected_value", "expected_value"]


def build_baseline(seed: int, scale: dict) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Clean, rule-following dataset. Returns (tables, pre-drawn values)."""
    tables = build_master(seed, scale)                                      # master data
    tickets, draws = build_tickets(seed, scale, tables["customer"])         # arrivals
    sim = simulate(tickets, draws, tables, scale["days"] * C.DAY)           # routing
    events = sim["assignment_event"]
    messages = build_messages(tickets, events, sim["first_response"], draws, scale["messages"])
    derive_ticket_columns(tickets, events, messages)                       # snapshot columns
    sla_headers, sla_events = build_sla(tickets, events)                    # SLA records
    apply_csat(tickets, events, sla_events, sim["resolution"], draws)       # CSAT
    tables |= {"ticket": tickets, "sla": sla_headers, "assignment_event": events,
               "sla_event": sla_events, "message": messages, "resolution": sim["resolution"]}
    return tables, draws


def run_checks(db: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    return structural_checks(db), business_checks(db)


def generate(scale_name: str, seed: int, out: Path) -> dict:
    scale = C.SCALES[scale_name]
    info = {"generator": f"python -m caserouting generate --scale {scale_name} --seed {seed}",
            "scale": scale_name, "seed": seed, "parameters": scale,
            "external_data": "none: every record is synthetic; language codes follow ISO 639-1"}

    tables, _ = build_baseline(seed, scale)
    base_structural, base_findings = run_checks(to_export_rows(tables))
    if base_structural or base_findings:
        raise RuntimeError(f"baseline is not clean: {(base_structural + base_findings)[:5]}")

    decisions = expected_decisions(tables)
    gt = inject(tables, seed, scale["anomalies_per_type"])

    out.mkdir(parents=True, exist_ok=True)
    write_dataset(out, tables)
    gt_dir = out / "ground_truth"
    write_csv(gt_dir / "ground_truth.csv", gt, GT_COLUMNS)
    write_json(gt_dir / "ground_truth.json", gt)
    write_csv(gt_dir / "expected_decisions.csv", decisions, list(decisions[0]))
    write_json(gt_dir / "expected_decisions.json", decisions)

    db = load_dir(out)                     # validate what was written, not what is in memory
    structural, findings = run_checks(db)
    detection = score(findings, gt)
    m = metrics(db, detection)
    write_json(out / "validation" / "findings.json",
               sorted(findings, key=lambda f: (f["issue_type"], f["ticket_id"], f["check"])))
    write_json(out / "validation" / "structural_failures.json", structural)
    write_json(out / "metrics.json", m)
    (out / "validation_summary.md").write_text(
        summary_markdown(info, structural, len(base_findings), findings, detection, m), encoding="utf-8")
    return write_manifest(out, info | {"baseline_findings": len(base_findings),
                                       "structural_failures": len(structural)})
