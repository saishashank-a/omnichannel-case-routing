# Agent-generated 003 — schema.sql + data dictionary + model docs

- **Tool:** Claude Code sub-agent (Opus 5.5), spawned by the main session
- **Sent:** 2026-11-12 ~08:40 CST (Chicago)

---

In the repo /Users/saishashankanchuri/dev/omnichannel-case-routing write exactly three files: `caserouting/schema.sql`, `docs/data_dictionary.md`, `docs/model.md`. Touch NO other files (others are editing the repo in parallel). Do not commit. Read `caserouting/config.py` and `caserouting/ids.py` first: every allowed value, unit and ID format you document must match them exactly. Also read `prompts/002-problem-statement.md` (the assignment).

Project: synthetic omnichannel support-ticket generator + routing/SLA simulator. Stdlib Python writes CSV/JSON and loads this DDL into SQLite. All timestamps are stored as TEXT ISO-8601 UTC "2026-01-03T14:05:00Z". Durations/targets are INTEGER minutes. Booleans are INTEGER 0/1.

## Tables (exact names and columns, in this order; PK first)
Reference / master:
- channel(channel_id PK [EMAIL|CHAT|PHONE], name, default_max_concurrent INT)
- language(language_code PK [en|es|fr|de], name)
- skill(skill_id PK, name)
- queue(queue_id PK, name, skill_id FK->skill)
- intent(intent_id PK, queue_id FK->queue, default_priority [P1..P4], is_safety 0/1)
- priority_rule(rule_id PK, description, effective_from TEXT, effective_to TEXT NULL)
- sla_policy(priority, channel_id FK->channel, first_response_min INT, resolution_min INT, calendar ['24x7'|'CHANNEL'], PK(priority, channel_id))  -- added table, not in the spec's entity list
- shift(shift_id PK, start_min INT, end_min INT, weekdays TEXT e.g. "0,1,2,3,4,5")  -- added
- customer(customer_id PK, display_name, customer_type [CUSTOMER|PROSPECT], tier [STANDARD|PREMIUM|ENTERPRISE] NULL only for PROSPECT, preferred_language FK->language, created_at)
- agent(agent_id PK, display_name, shift_id FK->shift, max_concurrent_email INT, max_concurrent_chat INT, max_concurrent_phone INT, hired_at TEXT, status [ACTIVE])
- agent_skill(agent_id FK, skill_id FK, effective_from TEXT, PK(agent_id, skill_id))  -- bridge N:M
- agent_language(agent_id FK, language_code FK, effective_from TEXT, PK(agent_id, language_code))  -- bridge N:M
Transactions / events:
- ticket(ticket_id PK, customer_id FK, channel_id FK, intent_id FK, language_code FK, urgency [LOW|MEDIUM|HIGH], priority [P1..P4], priority_rule_id FK->priority_rule, created_at, after_hours 0/1, status [QUEUED|ASSIGNED|RESOLVED|REOPENED], current_queue_id FK->queue, transfer_count, escalation_count, reopen_count INT, first_response_at NULL, resolved_at NULL, csat INT 1..5 NULL)
- sla(sla_id PK "SLA-<ticket-id>", ticket_id FK UNIQUE (1:1), priority, channel_id, calendar ['24x7'|'CHANNEL'], first_response_target_min, resolution_target_min, started_at, first_response_due_at, resolution_due_at)
- assignment_event(asn_id PK, ticket_id FK, seq INT, event_type [ASSIGN|TRANSFER|ESCALATE|RESOLVE|REOPEN], ts, queue_id FK, agent_id FK NULL, translation_flag 0/1, reason TEXT; UNIQUE(ticket_id, seq))
- sla_event(sla_event_id PK, sla_id FK->sla, ticket_id FK, cycle_no INT, event_type [CLOCK_STARTED|FIRST_RESPONSE_MET|FIRST_RESPONSE_BREACHED|RESOLUTION_MET|RESOLUTION_BREACHED|CLOCK_RESTARTED], ts, due_at NULL)
- message(message_id PK, ticket_id FK, seq INT, ts, author_type [CUSTOMER|AGENT|SYSTEM], channel_id FK, agent_id FK NULL, body TEXT; UNIQUE(ticket_id, seq))
- resolution(resolution_id PK "RES-<ticket-id>-001", ticket_id FK, cycle_no INT, agent_id FK, resolved_at, handle_minutes INT, resolution_code [SOLVED|WORKAROUND|INFO_PROVIDED], csat INT 1..5 NULL; UNIQUE(ticket_id, cycle_no))

## schema.sql
SQLite DDL: CREATE TABLE in the order above (parents first), PRIMARY KEY, FOREIGN KEY REFERENCES, NOT NULL where required, CHECK constraints for every enum and 0/1 flag and csat range, UNIQUE as listed. Short `--` comment per table. No indexes beyond what PK/UNIQUE give. It must execute cleanly: verify with `cd /Users/saishashankanchuri/dev/omnichannel-case-routing && uv run python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.executescript(open('caserouting/schema.sql').read()); print('ok')"`.

## docs/data_dictionary.md
One section per table. A markdown table per section with columns: Field | Type | Required | Allowed values / format | Units | Unique | Validation rule. Every column of every table above must appear (a test will check this mechanically against schema.sql column names, so spell them identically and put each field name in backticks in the Field column). Mark derived columns (ticket.status, current_queue_id, *_count, first_response_at, resolved_at, csat, all sla due times) as "Derived from <source> by <rule>" in the validation-rule cell — ticket columns are a snapshot computed from the append-only event tables, never edited independently. Note at top: seed 20261022, time model (UTC minutes since 2026-01-01T00:00Z, exported as ISO), and that ground-truth anomaly labels live only in `ground_truth/` and never in these tables.

## docs/model.md
- Mermaid `erDiagram` with every table and relationship (crow's-foot cardinalities, optional where FK nullable).
- Cardinality table: Relationship | Type (1:1, 1:N, N:M via bridge) | Optional? | Notes.
- Effective dates: which tables carry them and what they mean.
- Ticket lifecycle: states QUEUED, ASSIGNED, RESOLVED, REOPENED and the allowed transitions driven by assignment_event.event_type: ASSIGN (QUEUED|REOPENED -> ASSIGNED), TRANSFER (ASSIGNED -> QUEUED, new queue), ESCALATE (ASSIGNED|QUEUED|REOPENED -> QUEUED in QUE-T2), RESOLVE (ASSIGNED -> RESOLVED), REOPEN (RESOLVED -> REOPENED). A new ticket starts QUEUED with no event. Include a Mermaid stateDiagram-v2.
- SLA lifecycle: sla_event types, cycle_no increments on reopen (CLOCK_RESTARTED).
- Generation order (parents before children): reference tables -> customer, agent, bridges -> ticket + sla -> assignment_event + resolution (routing) -> sla_event -> message.
Keep prose short and plain. Report back: files written, the sqlite check output, and any place where config.py contradicted this brief.
