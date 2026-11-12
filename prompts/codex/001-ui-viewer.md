# Codex — 001 — Results viewer UI

- **Tool:** Codex CLI 0.167.2
- **Model:** gpt-6-luna (reasoning effort: medium) — confirm with /status
- **Sent:** <fill in time, America/Chicago>
- **Written by:** Claude Code (Opus 5.5) at my request (rewritten once, see prompt 013); sent by me verbatim

---

# Task: build a read-only results viewer in `ui/`

## Context
This repo (`omnichannel-case-routing`) is a Python simulator of a customer-support centre. It generates synthetic tickets (email, chat, phone), routes each to an agent by skill, language and capacity, tracks SLA deadlines, simulates transfers, escalations and reopens, then plants 5 kinds of rule-breaking anomalies and runs a checker that should find exactly them. The Python code is being written in parallel by someone else and writes JSON files. You build a viewer that lets a reviewer explore those files.

## Rules
1. Create or edit files **only inside `ui/`**. Do not read, change or run anything else in the repo except to serve it.
2. Exactly three source files: `ui/index.html`, `ui/app.js`, `ui/style.css`. Vanilla JS (ES2020) and plain CSS. No frameworks, no npm, no build step, no CDN links. It must work offline.
3. Keep `app.js` under 600 lines, with short plain comments. No classes or abstractions that aren't needed.
4. Read-only: it only loads and displays data.
5. Never crash on missing data:
   - A missing file shows a visible message in the page.
   - A missing field shows "—".
   - Extra fields are ignored.

## How it runs
- From the repo root: `python3 -m http.server 8000`, then open `http://localhost:8000/ui/`.
- The `?data=<folder>` query parameter picks the dataset. Default is `../data/starter`; `?data=sample` loads `ui/sample`.
- Load everything with `fetch()` on startup. Build `Map` lookups by `ticket_id` once.
- Must stay responsive at 30,000 tickets: paginate the ticket list at 100 rows per page.

## Data contract (do not change names)
Each table is a JSON array of flat objects at `<data>/json/<table>.json`. Timestamps are UTC ISO strings like `"2026-01-03T14:05:00Z"`. Nullable fields are `null`.

- **ticket.json** — `ticket_id` ("TKT-2026-000001"), `customer_id` ("CUS-000001"), `channel_id` (EMAIL|CHAT|PHONE), `intent_id` ("INT-BILLING"), `language_code` ("en"), `urgency` (LOW|MEDIUM|HIGH), `priority` (P1|P2|P3|P4), `created_at`, `after_hours` (0|1), `status` (QUEUED|ASSIGNED|RESOLVED|REOPENED), `current_queue_id` ("QUE-BILLING"), `transfer_count`, `escalation_count`, `reopen_count` (ints), `first_response_at`, `resolved_at` (nullable), `csat` (1–5 or null)
- **assignment_event.json** — `asn_id` ("ASN-TKT-2026-000001-001"), `ticket_id`, `seq` (1,2,3…), `event_type` (ASSIGN|TRANSFER|ESCALATE|RESOLVE|REOPEN), `ts`, `queue_id`, `agent_id` ("AGT-000001" or null), `translation_flag` (0|1), `reason`
- **sla_event.json** — `sla_event_id` ("SLA-TKT-2026-000001-001"), `sla_id` ("SLA-TKT-2026-000001"), `ticket_id`, `cycle_no`, `event_type` (CLOCK_STARTED|FIRST_RESPONSE_MET|FIRST_RESPONSE_BREACHED|RESOLUTION_MET|RESOLUTION_BREACHED|CLOCK_RESTARTED), `ts`, `due_at` (nullable)
- **message.json** — `message_id` ("MSG-TKT-2026-000001-001"), `ticket_id`, `seq`, `ts`, `author_type` (CUSTOMER|AGENT|SYSTEM), `channel_id`, `agent_id` (nullable), `body`
- **agent.json** — `agent_id`, `display_name`, `shift_id` (SHF-DAY|SHF-EVE|SHF-NIGHT), `max_concurrent_email`, `max_concurrent_chat`, `max_concurrent_phone`

Other files:
- **`<data>/metrics.json`** — one object. Render any keys present. Known keys:
  - `sla_attainment`: `[{channel_id, priority, met, breached, pct}]`
  - `rates`: `{transfer_rate, escalation_rate, reopen_rate, language_match_rate, translation_rate}`
  - `queue_wait_minutes`: `{p50, p90, p99}`
  - `csat_distribution`: `{"1":n … "5":n}`
  - `peak_concurrency`: `[{agent_id, channel_id, peak, limit}]`
  - `anomaly_detection`: `[{issue_type, expected, found, missed, false_positive}]`
- **`<data>/ground_truth/ground_truth.json`** — `[{anomaly_id, issue_type, ticket_id, entity_table, entity_id, rule_violated, field, injected_value, expected_value}]`
- **`<data>/validation/findings.json`** — `[{issue_type, ticket_id, check, detail}]`

## Screens: three tabs

**1. Overview**
- Headline cards: tickets, messages, agents, anomalies expected vs found.
- SLA attainment table, channel × priority. Shade the % cell: green ≥ 90, amber 75–90, red < 75.
- Rates, wait percentiles and CSAT distribution as small tables or CSS bars. No chart library.

**2. Tickets**
- Filters:
  - channel, priority and status
  - has transfer, has escalation, reopened, after hours
  - "anomaly", meaning the ticket is in ground truth
- Search box for ticket ID.
- Clicking a row opens a detail panel:
  - Header: the ticket fields, plus one badge per ground-truth anomaly on that ticket.
  - **One merged timeline** of assignment events, SLA events and messages for the ticket. Sort by `ts`; on equal `ts`, put assignment before SLA before message.
  - Colour-code timeline rows by source. Show agent, queue, translation flag and SLA due time where present.

**3. Anomalies**
- Join ground truth and findings on `(issue_type, ticket_id)`. Label each row:
  - **caught**: in both
  - **missed**: ground truth only
  - **false alarm**: findings only
- Per-issue_type summary counts.
- Clicking a row opens that ticket in the Tickets tab.

## Sample data (build against this first)
Create `ui/sample/` with the same layout (`json/`, `ground_truth/`, `validation/`, `metrics.json`), hand-written to match the contract exactly.
- 8 tickets covering:
  - every channel
  - one transfer, one escalation, one reopen
  - one after-hours arrival
  - one assignment with `translation_flag: 1`
- 2 ground-truth anomalies: one caught, one missed.
- 1 false alarm in findings.

## Done when
- `/ui/?data=sample` shows all three tabs working, with zero console errors.
- Filters, pagination, the timeline and the anomaly → ticket jump all work on the sample.
- `ui/README.md` (under 30 lines) explains how to run it and lists the files it reads.
- `git status` shows changes only under `ui/`.

When finished, reply with a short summary of the files created and anything you could not do.
