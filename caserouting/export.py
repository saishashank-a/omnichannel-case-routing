"""Write the dataset: CSV, JSON, a SQLite database and a plain-SQL seed file.

schema.sql is the single source of truth for table order and column order.
Rows whose keys differ from the schema columns stop the export, so the code,
the DDL and the data dictionary cannot silently drift apart.

Everything written is deterministic (sorted rows, fixed formatting, no wall
clock), so two runs with the same seed produce byte-identical files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

from .bizhours import to_iso

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Internal times are int minutes; these columns are exported as ISO-8601 UTC.
TIME_COLUMNS = {"created_at", "ts", "due_at", "first_response_at", "resolved_at", "started_at",
                "first_response_due_at", "resolution_due_at"}


def schema_columns() -> dict[str, tuple[list[str], list[str]]]:
    """table -> (columns, primary-key columns), in schema (parent-first) order."""
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA_PATH.read_text())
    out = {}
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        info = con.execute(f"PRAGMA table_info({table})").fetchall()
        cols = [r[1] for r in info]
        pk = [r[1] for r in sorted((r for r in info if r[5]), key=lambda r: r[5])]
        out[table] = (cols, pk)
    return out


def to_export_rows(tables: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Check columns, convert times to ISO, sort by primary key."""
    out = {}
    for table, (cols, pk) in schema_columns().items():
        rows = []
        for r in tables[table]:
            if list(r) != cols and set(r) != set(cols):
                raise ValueError(f"{table}: row keys {sorted(r)} != schema {cols}")
            rows.append({c: (to_iso(r[c]) if c in TIME_COLUMNS and isinstance(r[c], int) else r[c])
                         for c in cols})
        rows.sort(key=lambda r: tuple(str(r[c]) for c in pk))
        out[table] = rows
    return out


def _sql_literal(v: object) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c] for c in cols])


def write_dataset(out: Path, tables: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Write csv/, json/, seed.sql and caserouting.db. Returns the exported rows."""
    rows = to_export_rows(tables)
    schema = schema_columns()
    for table, (cols, _) in schema.items():
        write_csv(out / "csv" / f"{table}.csv", rows[table], cols)
        write_json(out / "json" / f"{table}.json", rows[table])

    # seed.sql: the DDL followed by INSERTs, parents first, so it loads with FKs on.
    lines = ["PRAGMA foreign_keys = ON;", "BEGIN TRANSACTION;", SCHEMA_PATH.read_text().strip()]
    for table, (cols, _) in schema.items():
        col_list = ", ".join(cols)
        for r in rows[table]:
            vals = ", ".join(_sql_literal(r[c]) for c in cols)
            lines.append(f"INSERT INTO {table} ({col_list}) VALUES ({vals});")
    lines.append("COMMIT;")
    (out / "seed.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Load the seed into SQLite with foreign keys enforced: a bad FK fails here.
    db = out / "caserouting.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript((out / "seed.sql").read_text(encoding="utf-8"))
    bad = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    if bad:
        raise ValueError(f"foreign key violations in SQLite load: {bad[:5]}")
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(out: Path, info: dict) -> dict:
    """Checksums and row counts of every deterministic output file.

    manifest.json itself and the binary .db are excluded: the manifest holds the
    checksums, and SQLite files can differ byte-wise with identical content.
    """
    files = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("manifest.json", "caserouting.db"):
            rel = p.relative_to(out).as_posix()
            entry = {"sha256": sha256(p)}
            if p.suffix == ".csv":
                entry["rows"] = sum(1 for _ in p.open(encoding="utf-8")) - 1
            files[rel] = entry
    manifest = info | {"files": files}
    write_json(out / "manifest.json", manifest)
    return manifest
