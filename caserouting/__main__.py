"""Command line: python -m caserouting {generate,validate,repro} [options]."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config as C


def cmd_generate(args: argparse.Namespace) -> int:
    from .pipeline import generate
    out = args.out or Path("data") / args.scale
    t0 = time.perf_counter()
    manifest = generate(args.scale, args.seed, out)
    rows = {k.removeprefix("csv/").removesuffix(".csv"): v["rows"]
            for k, v in manifest["files"].items() if k.startswith("csv/")}
    print(f"wrote {out} in {time.perf_counter() - t0:.1f}s")
    for table in ("ticket", "message", "agent", "assignment_event", "sla_event", "resolution"):
        print(f"  {table:<17} {rows[table]:>7}")
    detection = json.loads((out / "metrics.json").read_text())["anomaly_detection"]
    print(f"  baseline findings {manifest['baseline_findings']}, structural failures "
          f"{manifest['structural_failures']}")
    for d in detection:
        print(f"  {d['issue_type']:<26} expected {d['expected']:>3}  found {d['found']:>3}  "
              f"missed {d['missed']}  false+ {d['false_positive']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Re-check an existing dataset folder from its files only."""
    from .validate import business_checks, load_dir, score, structural_checks
    db = load_dir(args.dir)
    structural, findings = structural_checks(db), business_checks(db)
    gt_path = args.dir / "ground_truth" / "ground_truth.json"
    print(f"structural failures: {len(structural)}")
    for f in structural[:10]:
        print("  ", f)
    print(f"business-rule findings: {len(findings)}")
    if gt_path.exists():
        for d in score(findings, json.loads(gt_path.read_text())):
            print(f"  {d['issue_type']:<26} expected {d['expected']:>3}  found {d['found']:>3}  "
                  f"missed {d['missed']}  false+ {d['false_positive']}")
    return 1 if structural else 0


def cmd_repro(args: argparse.Namespace) -> int:
    """Generate twice in fresh processes (different hash seeds) and compare checksums."""
    with tempfile.TemporaryDirectory() as tmp:
        manifests = []
        for run, hashseed in ((1, "1"), (2, "2")):
            out = Path(tmp) / f"run{run}"
            subprocess.run([sys.executable, "-m", "caserouting", "generate", "--scale", args.scale,
                            "--seed", str(args.seed), "--out", str(out)],
                           check=True, capture_output=True, env={"PYTHONHASHSEED": hashseed, "PATH": ""})
            manifests.append(json.loads((out / "manifest.json").read_text()))
    a, b = manifests[0]["files"], manifests[1]["files"]
    same = a == b
    print(f"run 1: {len(a)} files, run 2: {len(b)} files")
    for name in sorted(set(a) | set(b)):
        if a.get(name) != b.get(name):
            print(f"  DIFFERENT {name}")
    print("identical: row counts and SHA-256 of every file match" if same else "NOT identical")
    return 0 if same else 1


def main() -> int:
    p = argparse.ArgumentParser(prog="caserouting", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate, inject, export and validate a dataset")
    g.add_argument("--scale", choices=sorted(C.SCALES), default="starter")
    g.add_argument("--seed", type=int, default=C.SEED)
    g.add_argument("--out", type=Path, default=None, help="output folder (default data/<scale>)")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="re-validate an existing dataset folder")
    v.add_argument("--dir", type=Path, default=Path("data/starter"))
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("repro", help="generate twice and compare checksums")
    r.add_argument("--scale", choices=sorted(C.SCALES), default="starter")
    r.add_argument("--seed", type=int, default=C.SEED)
    r.set_defaults(func=cmd_repro)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
