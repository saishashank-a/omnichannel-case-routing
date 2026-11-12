"""End to end on the starter scale: volumes, IDs, consistency, anomalies, reproducibility."""

import csv
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from caserouting import config as C
from caserouting.export import schema_columns
from caserouting.ids import PATTERNS
from caserouting.pipeline import build_baseline, generate
from caserouting.export import to_export_rows
from caserouting.validate import business_checks, structural_checks

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def out(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("starter")
    generate("starter", C.SEED, path)
    return path


def load(out: Path, table: str) -> list[dict]:
    return json.loads((out / "json" / f"{table}.json").read_text())


def test_volumes_match_scale(out):
    s = C.SCALES["starter"]
    assert len(load(out, "ticket")) == s["tickets"]
    assert len(load(out, "message")) == s["messages"]
    assert len(load(out, "agent")) == s["agents"]


def test_clean_baseline_has_no_findings():
    tables, _ = build_baseline(C.SEED, C.SCALES["starter"])
    rows = to_export_rows(tables)
    assert structural_checks(rows) == []
    assert business_checks(rows) == []


def test_every_anomaly_found_and_nothing_else(out):
    metrics = json.loads((out / "metrics.json").read_text())
    for row in metrics["anomaly_detection"]:
        assert row["expected"] == C.SCALES["starter"]["anomalies_per_type"]
        assert row["found"] == row["expected"] and row["missed"] == 0 and row["false_positive"] == 0
    findings = json.loads((out / "validation" / "findings.json").read_text())
    assert {f["issue_type"] for f in findings} == set(C.ANOMALY_TYPES)


def test_ground_truth_not_leaked_into_inputs(out):
    gt_fields = {"issue_type", "anomaly_id", "rule_violated", "injected_value", "expected_value"}
    for table, (cols, _) in schema_columns().items():
        assert not gt_fields & set(cols), table


def test_id_formats(out):
    for table, col, pattern in [("ticket", "ticket_id", "ticket_id"), ("message", "message_id", "message_id"),
                                ("agent", "agent_id", "agent_id"), ("assignment_event", "asn_id", "asn_id"),
                                ("sla", "sla_id", "sla_id")]:
        for r in load(out, table):
            assert PATTERNS[pattern].match(r[col]), r[col]
    for m in load(out, "message"):
        assert m["message_id"].startswith(f"MSG-{m['ticket_id']}-")


def test_ids_identical_across_csv_json_and_sql(out):
    con = sqlite3.connect(out / "caserouting.db")
    for table, (_, pk) in schema_columns().items():
        from_json = sorted(tuple(str(r[c]) for c in pk) for r in load(out, table))
        with (out / "csv" / f"{table}.csv").open() as f:
            from_csv = sorted(tuple(r[c] for c in pk) for r in csv.DictReader(f))
        from_sql = sorted(tuple(str(v) for v in row) for row in con.execute(f"SELECT {','.join(pk)} FROM {table}"))
        assert from_json == from_csv == from_sql, table


def test_data_dictionary_covers_every_column():
    text = (ROOT / "docs" / "data_dictionary.md").read_text()
    documented = set(re.findall(r"^\|\s*`(\w+)`", text, flags=re.M))
    for table, (cols, _) in schema_columns().items():
        missing = set(cols) - documented
        assert not missing, f"{table}: {missing}"


def test_required_scenarios_present(out):
    tickets = load(out, "ticket")
    events = load(out, "assignment_event")
    kinds = {e["event_type"] for e in events}
    assert {"TRANSFER", "ESCALATE", "REOPEN"} <= kinds
    assert any(e["translation_flag"] for e in events)                   # language mismatch
    assert any(t["intent_id"] == "INT-OUTAGE" for t in tickets)          # critical incidents
    assert any(t["after_hours"] for t in tickets)                        # after-hours arrivals


def test_repro_two_runs_identical():
    r = subprocess.run([sys.executable, "-m", "caserouting", "repro", "--scale", "starter"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "identical" in r.stdout
