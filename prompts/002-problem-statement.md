# 002 — Problem statement (pasted)

- **Tool:** Claude Code (CLI), model Claude Opus 5.5
- **Sent:** 2026-11-11 ~13:40 CST (Chicago)
- **Purpose:** supplied the authoritative problem statement (.txt), which was missing from prompt 001. Pasted verbatim below.

---

Business Context / Problem
Route email/chat/phone cases by intent, urgency, language, skill and agent capacity while tracking SLA.

Objective and Scope
Build a working solution for this end-to-end workflow: Route email/chat/phone cases by intent, urgency, language, skill and agent capacity while tracking SLA. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.

Primary Actors / Systems
Customer/prospect, marketing/sales operations, support agent, analyst and system administrator

Business Workflow and Rules
1. Generate/reference master data first: Customer, Channel, Ticket, Message, Intent.
2. Generate dependent transaction/event records using valid parent IDs.
3. Apply business logic: Generate tickets and threaded messages across channels; define intent/priority taxonomy and SLA calendars; define agent skills, languages, shifts and concurrency limits; assign tickets; simulate transfers, escalations and reopenings; record resolution and customer satisfaction.
4. Persist state changes as explicit records/events where relevant; do not overwrite history.
5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.

Entities and Relationships
Core entities: Customer, Channel, Ticket, Message, Intent, Language, PriorityRule, Agent, Skill, Queue, AssignmentEvent, SLAEvent, Resolution. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.

ID / Nomenclature Conventions
TKT-2026-000001; MSG-<ticket-id>-001; AGT-000001; ASN-<ticket-id>-001; SLA-<ticket-id>.

Synthetic Data Generation Instructions (Granular)
Step 1 — Write a data dictionary for: Customer, Channel, Ticket, Message, Intent, Language, PriorityRule, Agent, Skill, Queue, AssignmentEvent, SLAEvent, Resolution. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule.
Step 2 — Create parent/master tables first, then child and event tables. Apply this domain-specific generation logic: Generate tickets and threaded messages across channels; define intent/priority taxonomy and SLA calendars; define agent skills, languages, shifts and concurrency limits; assign tickets; simulate transfers, escalations and reopenings; record resolution and customer satisfaction.
Step 3 — Apply deterministic IDs and naming: TKT-2026-000001; MSG-<ticket-id>-001; AGT-000001; ASN-<ticket-id>-001; SLA-<ticket-id>. Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.
Step 4 — Generate the baseline volume: Generate 30,000 tickets, 100 agents, 100,000 messages and 90 days of events. Include language mismatch, critical incidents, queue spikes and after-hours arrivals. Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator.
Step 5 — Generate valid baseline records first, then inject labelled edge cases: Agent assigned beyond capacity; SLA ignores channel calendar; reopened ticket loses history; transfer loop; priority contradicts defined safety rule.
Step 6 — Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently.
Step 7 — Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.
Step 8 — Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.
Step 9 — Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
Step 10 — Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.

Suggested Volume and Coverage
Generate 30,000 tickets, 100 agents, 100,000 messages and 90 days of events. Include language mismatch, critical incidents, queue spikes and after-hours arrivals.

Required Edge Cases / Negative Scenarios
Agent assigned beyond capacity; SLA ignores channel calendar; reopened ticket loses history; transfer loop; priority contradicts defined safety rule.

Validation Rules / Acceptance Criteria
Routing respects skill/capacity; SLA is reproducible; escalation timing is correct; assignment history is complete.

Evaluation Focus for Generated Data
Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance.

Public Data Guidance / Lawful Use
External data is optional. If used, record source URL, dataset/version, retrieval date, license/terms, attribution, transformations and fields discarded. Use only data you are legally permitted to access and redistribute; do not bypass access controls or collect confidential/personal information. If licensing or suitability is unclear, use synthetic data and cite public reference data only for schema inspiration.
Before you submit, make sure you have
Pushed your code to a public GitHub repository
Added a README explaining how to run it
Included any tests the problem asks for
