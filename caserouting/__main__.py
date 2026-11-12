"""Command line: python -m caserouting <command> [options]."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import config as C
from .pipeline import generate


def main() -> None:
    p = argparse.ArgumentParser(prog="caserouting", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate, simulate, validate and export a dataset")
    g.add_argument("--scale", choices=sorted(C.SCALES), default="starter")
    g.add_argument("--seed", type=int, default=C.SEED)
    g.add_argument("--out", type=Path, default=None, help="output folder (default data/<scale>)")

    args = p.parse_args()
    if args.command == "generate":
        out = args.out or Path("data") / args.scale
        t0 = time.perf_counter()
        manifest = generate(args.scale, args.seed, out)
        rows = {k.split("/")[-1].removesuffix(".csv"): v["rows"]
                for k, v in manifest["files"].items() if k.startswith("csv/")}
        print(f"wrote {out} in {time.perf_counter() - t0:.1f}s")
        for table in ("ticket", "message", "agent", "assignment_event", "sla_event", "resolution"):
            print(f"  {table:<17} {rows[table]:>7}")


if __name__ == "__main__":
    main()
