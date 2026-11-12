# Codex / Gemini CLI — 001 — Results viewer UI

- **Tool:** Codex CLI or Gemini CLI (record which one, and the model, here when sent)
- **Sent:** <fill in time, America/Chicago>
- **Written by:** Claude Code (Opus 5.5) at my request; sent by me verbatim

---

You are building a small, read-only results viewer for an existing Python project in this repo (`omnichannel-case-routing`). The Python side is being written in parallel by someone else. **Only create or edit files under `ui/`. Do not touch any other folder.**

## What the project is

A simulator for a customer-support centre. It generates synthetic support tickets (email, chat, phone), routes each to an agent by skill, language and capacity, tracks SLA deadlines, simulates transfers, escalations and reopens, then deliberately plants 5 kinds of rule-breaking anomalies and runs a checker that should find exactly them. Output is CSV/JSON files plus `metrics.json`. The viewer helps a reviewer explore that output.

## Hard constraints

- **One static page, no build step, no framework, no npm.** `ui/index.html` + `ui/app.js` + `ui/style.css`. Vanilla JS (ES2020), plain CSS. No CDN dependencies, so it works offline.
- Loads data with `fetch()` from relative paths. Run with `python3 -m http.server 8000` from the repo root and open `http://localhost:8000/ui/`. A `?data=` query parameter selects the dataset folder; default `../data/starter`.
- **Read-only.** Never modifies data.
- Must handle ~1,000 tickets smoothly; must not freeze on 30,000 (paginate or virtualise the ticket list; build lookup maps once with `Map`).
- Code must be short and plainly commented. Target under 600 lines of JS total. No clever abstractions.
- Missing files must show a clear message in the page, not a blank screen.

## Data contract (JSON files the Python side will produce)

Every table is a JSON array of flat objects, sorted by primary key, at `<data>/json/<table>.json`. Timestamps are ISO-8601 UTC strings like `"2026-01-03T14:05:00Z"`. Nullable fields are `null`.

`ticket.json`
```
ticket_id "TKT-2026-000001", customer_id "CUS-000001", channel_id "EMAIL"|"CHAT"|"PHONE",
intent_id "INT-BILLING", language_code "en", urgency "LOW"|"MEDIUM"|"HIGH",
priority "P1"|"P2"|"P3"|"P4", created_at, after_hours 0|1, status "QUEUED"|"ASSIGNED"|"RESOLVED"|"REOPENED",
current_queue_id "QUE-BILLING", transfer_count int, escalation_count int, reopen_count int,
first_response_at|null, resolved_at|null, csat 1..5|null
```

`assignment_event.json` (append-only history, one row per step)
```
asn_id "ASN-TKT-2026-000001-001", ticket_id, seq int (1,2,3…), event_type "ASSIGN"|"TRANSFER"|"ESCALATE"|"RESOLVE"|"REOPEN",
ts, queue_id, agent_id "AGT-000001"|null, translation_flag 0|1, reason string
```

`sla_event.json`
```
sla_event_id "SLA-TKT-2026-000001-001", sla_id "SLA-TKT-2026-000001", ticket_id, cycle_no int,
event_type "CLOCK_STARTED"|"FIRST_RESPONSE_MET"|"FIRST_RESPONSE_BREACHED"|"RESOLUTION_MET"|"RESOLUTION_BREACHED"|"CLOCK_RESTARTED",
ts, due_at|null
```

`message.json`
```
message_id "MSG-TKT-2026-000001-001", ticket_id, seq int, ts, author_type "CUSTOMER"|"AGENT"|"SYSTEM",
channel_id, agent_id|null, body string
```

`agent.json`
```
agent_id, display_name, shift_id "SHF-DAY"|"SHF-EVE"|"SHF-NIGHT", max_concurrent_email int, max_concurrent_chat int, max_concurrent_phone int
```

`<data>/metrics.json` — an object. Render whatever keys exist; known ones:
```
{ "sla_attainment": [{"channel_id","priority","met","breached","pct"}],
  "rates": {"transfer_rate","escalation_rate","reopen_rate","language_match_rate","translation_rate"},
  "queue_wait_minutes": {"p50","p90","p99"},
  "csat_distribution": {"1":n,"2":n,"3":n,"4":n,"5":n},
  "peak_concurrency": [{"agent_id","channel_id","peak","limit"}],
  "anomaly_detection": [{"issue_type","expected","found","missed","false_positive"}] }
```

`<data>/ground_truth/ground_truth.json` — array of `{anomaly_id, issue_type, ticket_id, entity_table, entity_id, rule_violated, field, injected_value, expected_value}`.

`<data>/validation/findings.json` — array of `{issue_type, ticket_id, check, detail}` (what the checker found).

Treat any extra fields as display-only. If a field is missing, show "—" rather than crashing.

## Screens (three tabs)

1. **Overview**
   - Headline counts: tickets, messages, agents, anomalies expected vs found.
   - SLA attainment table, channel × priority, with the percentage cell shaded (plain CSS background, green ≥ 90, amber 75–90, red < 75).
   - Rates, wait percentiles and CSAT distribution as simple tables or CSS bar rows (no chart library).

2. **Tickets**
   - Filterable list: by channel, priority, status, "has transfer", "has escalation", "reopened", "after hours", "anomaly". The anomaly filter uses ground truth ticket IDs. Plus a text search on ticket ID.
   - Click a ticket to open a detail panel showing one **merged timeline** sorted by `ts`, then by type order ASN < SLA < MSG for equal timestamps. Each row is colour-coded by source (assignment / SLA / message) and shows agent, queue, translation flag and SLA due time.
   - Detail header: ticket fields, plus a badge per ground-truth anomaly on that ticket.

3. **Anomalies**
   - Table joining ground truth with findings on `(issue_type, ticket_id)`. Status per row: **caught** (in both), **missed** (ground truth only), **false alarm** (findings only).
   - Summary per issue_type. Click a row to jump to that ticket in the Tickets tab.

## Test fixtures (so you can build before real data exists)

Create `ui/sample/` with a hand-written mini dataset that follows the contract exactly, under the same folder layout (`json/`, `ground_truth/`, `validation/`, `metrics.json`):
- 8 tickets covering every channel, a transfer, an escalation, a reopen, an after-hours arrival and a translation-flagged assignment.
- At least 2 ground-truth anomalies, one caught and one missed.
- 1 false alarm.

`?data=sample` must load it.

## Done when

- `python3 -m http.server 8000` then `/ui/?data=sample` shows all three tabs working with no console errors.
- `ui/README.md` (under 30 lines) explains how to run it and lists the files it reads.
- No files outside `ui/` were changed.
