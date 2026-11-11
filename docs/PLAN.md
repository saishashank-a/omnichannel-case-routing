# Case Routing: 72h Plan (Chicago time)

Deadline is **Sat Nov 14 03:41 CST**. Target is **Fri 22:00**. v1 should be tagged by **Thu 22:30**. Repo: `omnichannel-case-routing`, package `caserouting/`.

**Conflict resolutions** (when the analyses disagreed, I took the simpler option that still meets the acceptance criteria):

| Topic | Options proposed | Chosen | Why |
|---|---|---|---|
| Libraries | numpy+pandas / stdlib | **stdlib only**, pytest for dev | Data size is small. Avoids the risk of missing 3.15 wheels. Every line stays explainable. |
| Config | YAML / TOML / `config.py` | **`config.py` constants** | No loader and no schema layer. Rules sit next to the code. |
| Runner | Makefile / argparse | **argparse** (`generate`, `validate`, `repro`) | One fewer file. |
| RNG | numpy SeedSequence / `random` | **`random.Random(f"{seed}:{stage}")`** per stage | Seeding from a string uses sha512, not `hash()`, so it is stable. |
| Routing | full DES with waiting heaps / heapq of requests with busy-until slots | **heapq of routing requests + per-agent busy-until slots** | About 150 lines. Priority is the heap tiebreak on retry. The limitation is documented. |
| SLA | live timers (pause/warn) / post-pass | **pure post-pass in `sla.py`** | Reproducible by construction. Pause and warning are cut. |
| Escalation threshold | 75% / 80% | **80% of resolution target, in business time** | Any value works. 80% is fixed and documented. |
| Timezone/horizon | America/Chicago Aug–Oct / UTC Jan–Mar | **UTC, no DST, 2026-01-01 to 2026-03-31 (exactly 90 days)** | No DST. Holidays Jan 1, Jan 19, Feb 16 fall inside. `TKT-2026` prefix is consistent. |
| Message total | ±3% / exact | **exactly 100,000** (deterministic top-up or trim) | Cheap, and reconciliation is clean. |
| Anomaly volume | % rates / fixed | **fixed counts: full 30 per type, starter 5 per type**, disjoint tickets | Predictable and easy to test. |
| Detectors | separate modules / validators | **validators are the detectors** | Clean baseline gives 0 findings. Injected data must give findings equal to ground truth. |
| Data dictionary | generated from `schema.py` / hand-written + drift test | **hand `schema.sql` + `docs/data_dictionary.md` + drift test** | DDL is the artifact reviewers read. |
| Occupancy metric | occupancy + assert / peak concurrency | **peak concurrency vs limit**. SLA attainment is the calibration target (85–95%). | Occupancy denominator is fiddly. |
| Reports location | `reports/` / `data/<scale>/` | **`data/<scale>/metrics.json` + `validation_summary.md`** | One fewer folder. |
| Python | 3.11 / 3.12 | **`uv python pin 3.12`**, `requires-python>=3.11` | Stdlib only, so low risk either way. |

---

## 1. Requirements checklist

### PS-Context / PS-Objective
1. [ ] Route email, chat and phone by intent (PS-Context)
2. [ ] Route by urgency (PS-Context)
3. [ ] Route by language (PS-Context)
4. [ ] Route by skill (PS-Context)
5. [ ] Route by agent capacity (PS-Context)
6. [ ] Track SLA for every case (PS-Context)
7. [ ] Working end-to-end solution, not a fragment (PS-Objective)
8. [ ] Outputs expose key decisions: routing, priority, escalation (PS-Objective)
9. [ ] Exceptions exposed explicitly (PS-Objective)
10. [ ] Each decision traces back to its rule and input (PS-Objective)
11. [ ] Measurable outputs / metrics (PS-Objective)
12. [ ] Multiple related entities (PS-Objective)
13. [ ] Conditional rules (PS-Objective)
14. [ ] At least one exception path (PS-Objective)
15. [ ] Meaningful evaluation metrics (PS-Objective)

### PS-Actors
16. [ ] Customer/prospect; a prospect may have no account (PS-Actors)
17. [ ] Marketing/sales ops (PS-Actors)
18. [ ] Support agent (PS-Actors)
19. [ ] Analyst consumes report and metrics (PS-Actors)
20. [ ] Sysadmin owns config, rules, calendars and queues (PS-Actors)

### PS-Workflow
21. [ ] Master data first: Customer, Channel, Ticket, Message, Intent (PS-Workflow-1)
22. [ ] Dependent records use only valid parent IDs (PS-Workflow-2)
23. [ ] Generate tickets (PS-Workflow-3)
24. [ ] Threaded messages across channels (PS-Workflow-3)
25. [ ] Intent taxonomy (PS-Workflow-3)
26. [ ] Priority taxonomy (PS-Workflow-3)
27. [ ] SLA calendars (PS-Workflow-3)
28. [ ] Agent skills (PS-Workflow-3)
29. [ ] Agent languages (PS-Workflow-3)
30. [ ] Agent shifts (PS-Workflow-3)
31. [ ] Agent concurrency limits (PS-Workflow-3)
32. [ ] Assign tickets (PS-Workflow-3)
33. [ ] Simulate transfers (PS-Workflow-3)
34. [ ] Simulate escalations (PS-Workflow-3)
35. [ ] Simulate reopenings (PS-Workflow-3)
36. [ ] Record resolution (PS-Workflow-3)
37. [ ] Record CSAT (PS-Workflow-3)
38. [ ] State changes stored as explicit records or events (PS-Workflow-4)
39. [ ] Never overwrite history; append-only event tables (PS-Workflow-4)
40. [ ] Outcomes come from documented rules, not independent random draws (PS-Workflow-5)
41. [ ] Ground-truth labels come from documented rules (PS-Workflow-5)

### PS-Entities
42. [ ] All 13 entities: Customer, Channel, Ticket, Message, Intent, Language, PriorityRule, Agent, Skill, Queue, AssignmentEvent, SLAEvent, Resolution (PS-Entities)
43. [ ] PK on every entity (PS-Entities)
44. [ ] FK on every relationship (PS-Entities)
45. [ ] Cardinality documented (PS-Entities)
46. [ ] Optional relationships documented (PS-Entities)
47. [ ] Effective dates documented (PS-Entities)
48. [ ] Lifecycle states and transitions documented (PS-Entities)
49. [ ] Bridge tables for N:M: agent_skill, agent_language, queue_skill (PS-Entities)
50. [ ] Event history for state changes (PS-Entities)
51. [ ] All joins validated (PS-Entities)
52. [ ] Anomalies labelled with issue_type and ground_truth (PS-Entities)
53. [ ] Injection does not corrupt unrelated rows (PS-Entities)

### PS-IDs
54. [ ] `TKT-2026-000001` (PS-IDs)
55. [ ] `MSG-<ticket-id>-001` (PS-IDs)
56. [ ] `AGT-000001` (PS-IDs)
57. [ ] `ASN-<ticket-id>-001` (PS-IDs)
58. [ ] `SLA-<ticket-id>` (PS-IDs)
59. [ ] Zero-padded counters (PS-Gen-3)
60. [ ] Immutable IDs (PS-Gen-3)
61. [ ] IDs match exactly across CSV, JSON and SQL (PS-Gen-3)

### PS-Gen (Steps 1–10)
62. [ ] Data dictionary for all 13 entities (PS-Gen-1)
63. [ ] Per field: type, required, allowed values, units, uniqueness, validation rule (PS-Gen-1)
64. [ ] Parents first, then children and events (PS-Gen-2)
65. [ ] Domain logic from items 23–37 (PS-Gen-2)
66. [ ] Deterministic IDs (PS-Gen-3)
67. [ ] 30,000 tickets (PS-Gen-4)
68. [ ] 100 agents (PS-Gen-4)
69. [ ] 100,000 messages (PS-Gen-4)
70. [ ] 90 days of events (PS-Gen-4)
71. [ ] Coverage: language mismatch (PS-Gen-4)
72. [ ] Coverage: critical incidents (PS-Gen-4)
73. [ ] Coverage: queue spikes (PS-Gen-4)
74. [ ] Coverage: after-hours arrivals (PS-Gen-4)
75. [ ] Seed 20261022, documented (PS-Gen-4)
76. [ ] Scale is a parameter; starter and full use the same generator (PS-Gen-4)
77. [ ] Clean baseline first, then injection (PS-Gen-5)
78. [ ] Edge case: agent beyond capacity, labelled (PS-Gen-5)
79. [ ] Edge case: SLA ignores channel calendar, labelled (PS-Gen-5)
80. [ ] Edge case: reopened ticket loses history, labelled (PS-Gen-5)
81. [ ] Edge case: transfer loop, labelled (PS-Gen-5)
82. [ ] Edge case: priority contradicts safety rule, labelled (PS-Gen-5)
83. [ ] Totals from source records (PS-Gen-6)
84. [ ] Balances from source records (PS-Gen-6)
85. [ ] Scores (CSAT, utilization) from source records (PS-Gen-6)
86. [ ] Statuses (ticket status, SLA met/breached) from source records (PS-Gen-6)
87. [ ] Dates (due, first response, resolved) from source records (PS-Gen-6)
88. [ ] Separate ground_truth.csv and ground_truth.json (PS-Gen-7)
89. [ ] Ground truth covers anomalies (PS-Gen-7)
90. [ ] Ground truth covers expected decisions (PS-Gen-7)
91. [ ] Ground truth covers labels (PS-Gen-7)
92. [ ] No leakage: no is_anomaly column in inputs (PS-Gen-7)
93. [ ] Validate PK uniqueness (PS-Gen-8)
94. [ ] Validate FK integrity (PS-Gen-8)
95. [ ] Validate enums (PS-Gen-8)
96. [ ] Validate date ordering (PS-Gen-8)
97. [ ] Validate arithmetic reconciliation (PS-Gen-8)
98. [ ] Validate lifecycle transitions (PS-Gen-8)
99. [ ] Check duplicates (PS-Gen-8)
100. [ ] Export CSV (PS-Gen-9)
101. [ ] Export JSON (PS-Gen-9)
102. [ ] Export SQL seed (PS-Gen-9)
103. [ ] README (PS-Gen-9)
104. [ ] Schema and data dictionary (PS-Gen-9)
105. [ ] Generator command documented (PS-Gen-9)
106. [ ] Seed documented (PS-Gen-9)
107. [ ] Source manifest (PS-Gen-9)
108. [ ] Validation summary (PS-Gen-9)
109. [ ] Regenerate twice with the same seed (PS-Gen-10)
110. [ ] Compare row counts and checksums; publish the result (PS-Gen-10)

### PS-Accept
111. [ ] Routing respects skill (PS-Accept)
112. [ ] Routing respects capacity (PS-Accept)
113. [ ] SLA reproducible: recomputing from events gives the same due and met values (PS-Accept)
114. [ ] Escalation timing correct (PS-Accept)
115. [ ] Assignment history complete (PS-Accept)

### PS-Eval
116. [ ] (a) Realistic distributions with meaningful variation (PS-Eval-a)
117. [ ] (b) Consistent IDs and valid joins (PS-Eval-b)
118. [ ] (c) Dependencies and lifecycles consistent (PS-Eval-c)
119. [ ] (d) Derived values correct and reconciled (PS-Eval-d)
120. [ ] (e) Normal, boundary, failure and exception coverage (PS-Eval-e)
121. [ ] (f) Ground truth kept separate (PS-Eval-f)
122. [ ] (g) Fixed-seed reproducibility (PS-Eval-g)
123. [ ] (g) Complete documentation (PS-Eval-g)
124. [ ] (g) Lawful provenance (PS-Eval-g)

### PS-PublicData
125. [ ] External data optional; if none is used, say so (PS-PublicData)
126. [ ] If used: source URL (PS-PublicData)
127. [ ] If used: dataset and version (PS-PublicData)
128. [ ] If used: retrieval date (PS-PublicData)
129. [ ] If used: license or terms (PS-PublicData)
130. [ ] If used: attribution (PS-PublicData)
131. [ ] If used: transformations (PS-PublicData)
132. [ ] If used: discarded fields (PS-PublicData)
133. [ ] Only data that can legally be used and redistributed (PS-PublicData)
134. [ ] No bypassing access controls (PS-PublicData)
135. [ ] No confidential or personal data (PS-PublicData)
136. [ ] Unclear licensing: synthetic data, cite public data only as inspiration (PS-PublicData)

### PS-Submit
137. [ ] Code in a public GitHub repo (PS-Submit)
138. [ ] README explains how to run (PS-Submit)
139. [ ] Tests: validation (Step 8), reproducibility (Step 10), acceptance criteria (PS-Submit)

### GL
140. [ ] Work and timestamps inside the 72h window (GL-00)
141. [ ] Code works and runs (GL-01)
142. [ ] Install steps (GL-01)
143. [ ] Configure steps (GL-01)
144. [ ] Run steps (GL-01)
145. [ ] Steps to verify key behavior (GL-01)
146. [ ] Public GitHub repo (GL-02)
147. [ ] Meaningful incremental commits, no squash dump (GL-02)
148. [ ] Design notes and decision log (GL-02)
149. [ ] Prompt history (GL-03)
150. [ ] Where AI accelerated the work (GL-03)
151. [ ] Where AI was relied on heavily (GL-03)
152. [ ] What was personally reviewed, changed and validated (GL-03)
153. [ ] Problem documented (GL-04)
154. [ ] Assumptions documented (GL-04)
155. [ ] Key decisions documented (GL-04)
156. [ ] Trade-offs documented (GL-04)
157. [ ] Testing approach documented (GL-04)
158. [ ] Limitations documented (GL-04)
159. [ ] How you know it works (GL-04)
160. [ ] Ready to walk through the solution (GL-04)

### FAQ
161. [ ] Deadline Sat Nov 14 03:41 CST (FAQ-1)
162. [ ] Repo stays public until the deadline; the latest version is evaluated (FAQ-2)
163. [ ] New dedicated public repo (FAQ-3)
164. [ ] Link sent from the recruitment email address (FAQ-3)
165. [ ] Follow the submission instructions (FAQ-3)
166. [ ] Clear directories: `prompts/`, `docs/` (FAQ-4)
167. [ ] Disclose AI tools used (FAQ-5)
168. [ ] ALL prompts to EVERY tool, including workflow and subagent prompts (FAQ-6)
169. [ ] Responses optional (FAQ-6)
170. [ ] Tool can't export: keep a reasonable record and disclose (FAQ-6)
171. [ ] Individual work only (FAQ-7)
172. [ ] Understand the core logic, design, dependencies and limitations (FAQ-7)
173. [ ] Only free or local services (FAQ-8)
174. [ ] No large or slow dependencies (FAQ-8)
175. [ ] Setup and run instructions (FAQ-9)
176. [ ] Show how core functionality was verified (FAQ-9)
177. [ ] Environment needs documented (FAQ-9)
178. [ ] Limitations documented (FAQ-9)
179. [ ] No imported complete solution or core-logic code (FAQ-10)
180. [ ] Respect licenses; attribute snippets (FAQ-10)
181. [ ] Reasonable assumptions, documented (FAQ-11)
182. [ ] If partial: what works, what is incomplete, limitations, next steps (FAQ-11)
183. [ ] Deviations from spec explained (FAQ-11)
184. [ ] No secrets in repo or `prompts/`; scrub logs (FAQ-12)
185. [ ] No PII: synthetic names, `example.com` emails (FAQ-12)
186. [ ] No proprietary code (FAQ-12)

---

## 2. Ambiguities and assumptions

| # | Ambiguity | Assumption |
|---|---|---|
| 1 | Ticket and Message listed as "master" | Generation order: reference (Channel, Language, Intent, Skill, Queue, PriorityRule) → Customer, Agent, bridges → Ticket → AssignmentEvent → SLAEvent → Message → Resolution. Documented. |
| 2 | 100k messages vs 30k tickets | At least 1 per ticket. Extra count per channel, top-up or trim to exactly 100,000. Starter target is about 3.33× tickets. |
| 3 | `SLA-<ticket-id>` vs many SLAEvents | `sla_id = SLA-TKT-…` (1:1 with ticket). SLAEvent PK = `SLA-TKT-…-001`. `cycle_no` column for reopens. |
| 4 | Long MSG IDs | Accept `MSG-TKT-2026-000001-001`. Cap of 999 per ticket, validated. |
| 5 | ASN semantics | AssignmentEvent PK. One row per ASSIGN, TRANSFER, ESCALATE, RESOLVE, REOPEN. Gapless per-ticket sequence. |
| 6 | Year in TKT | From created_at. Horizon is entirely 2026. Global counter. |
| 7 | Unspecified PKs | `CUS-000001`, `EMAIL/CHAT/PHONE`, ISO 639-1 (`en es fr de`), `INT-BILLING`, `SKL-TECH`, `QUE-BILLING-T1`, `PRL-001`, `SHF-DAY`, `RES-TKT-…-01`, `GT-0001`. Bridges use composite PKs. |
| 8 | Resolution with reopens | 1:N with ticket. `-01`, `-02` per cycle. CSAT on the final cycle only. |
| 9 | Timezone and horizon | UTC, no DST. 2026-01-01 00:00 to 2026-03-31 24:00 (arrivals). Resolution tail may spill into April; documented. |
| 10 | Holidays | Hardcoded list: Jan 1, Jan 19, Feb 16. No library. |
| 11 | Calendars | EMAIL Mon–Fri 08–18. CHAT and PHONE Mon–Sat 07–22. P1 safety/outage uses 24x7. SLA policy keyed on priority × channel. |
| 12 | After-hours | Arrival outside the channel calendar. Ticket created; SLA clock starts at the next open. `after_hours=1` column. |
| 13 | Urgency vs priority | Urgency (low/med/high) is an input signal. Priority P1–P4 = PriorityRule(intent, urgency, customer tier). Both stored. |
| 14 | Intent | Assigned by the generator from documented weights. No NLP. Message text is templated and not used for routing. |
| 15 | Safety rule (undefined) | Intents with `is_safety` (SAFETY, SECURITY, OUTAGE) have priority P1. Anything else is an anomaly. |
| 16 | Escalation | ASN `ESCALATE` to a Tier-2 queue at exactly `add_business_minutes(sla_start, 0.8 × resolution_target)` if the ticket is unresolved. Distinct from lateral TRANSFER. |
| 17 | "Routing respects skill/capacity" | At ASSIGN time: on shift, has the queue skill, language match or documented fallback, active count < limit. Violations exist only as labelled anomalies. |
| 18 | "SLA reproducible" | `sla.py` recompute from ticket, ASN and calendar gives identical due and met values. Seeded reruns have identical sha256. |
| 19 | "History complete" | Every assigned ticket has a seq starting at 001, gapless, with a valid transition chain. REOPEN is preceded by RESOLVE. |
| 20 | Language mismatch | Valid baseline. After waiting `LANG_FALLBACK_MIN`, any-language agent allowed with `translation_flag=1`. Counted in metrics. Not an anomaly. |
| 21 | Critical incident | Outage burst: INT-OUTAGE spike forced to P1 in a 1–4h window. Overlaps queue spikes. |
| 22 | Queue spike | Config windows with ×3–5 arrival weight for 1–4h. Listed in the manifest. |
| 23 | Transfer rule | Triage misroutes with pre-drawn p=0.08. The agent discovers it after k minutes and transfers to the correct queue. Baseline never revisits a queue. |
| 24 | Reopen rule | Pre-drawn p (higher when breached or transferred). Re-routed after a delay. `CLOCK_RESTARTED` under the same `sla_id`. |
| 25 | Marketing/sales actor | `customer_type=PROSPECT`. Intents `INT-SALES_INQUIRY`, `INT-DEMO_REQUEST` route to `QUE-SALES`. No login entity. |
| 26 | Sysadmin actor | `config.py` plus `config_hash` in the manifest. |
| 27 | Analyst actor | `metrics.json` and `validation_summary.md`. |
| 28 | Prospect without account | `CUS-` ID, type PROSPECT, `tier` null. |
| 29 | No SLA table in spec | SLA policy is a reference table `sla_policy` exported from config. Deviation documented. |
| 30 | Calendar and shift tables | Added: `channel_calendar`, `shift`, `agent_skill`, `agent_language`, `queue_skill`, `sla_policy`. Documented as additions. |
| 31 | Effective dates | `effective_from/to` on PriorityRule, agent_skill and sla_policy. Null `to` means current. Optional: one PRL version change on day 45. |
| 32 | Lifecycle | Ticket: `NEW→QUEUED→ASSIGNED→(TRANSFERRED|ESCALATED→QUEUED→ASSIGNED)*→RESOLVED→[REOPENED→QUEUED…]→CLOSED`. Open at horizon allowed. |
| 33 | SLA events | `CLOCK_STARTED`, `FIRST_RESPONSE_MET/BREACHED`, `RESOLUTION_MET/BREACHED`, `CLOCK_RESTARTED`. No pause or warning. Censored if open and `due ≥ horizon_end`. |
| 34 | "Balances/totals" | Totals: message, transfer, reopen counts, handle_minutes. Balance: agent active load = open ASN intervals. No money. |
| 35 | CSAT | `5 −1.5·breached −0.5·transfers −1·reopened −wait_penalty + noise{-1,0,0,0,1}`, clipped to 1–5. About 35% response rate, otherwise null. Only on resolved tickets. |
| 36 | Message author | `author_type` customer/agent/system. First message is from the customer. First agent message is at first-response time. Message channel may differ from ticket channel. |
| 37 | Anomaly count | Full: 30 per type. Starter: 5 per type. Disjoint tickets. Mutates baseline tickets, so totals stay exact. |
| 38 | Leakage | `issue_type` only in `ground_truth/`. Despite the PS-Entities wording, no flag columns in inputs. |
| 39 | Expected decisions | `ground_truth/expected_decisions.csv`: per ticket, the baseline `expected_priority`, `expected_queue`, `expected_resolution_due` (snapshot before injection). |
| 40 | Ground-truth columns | `anomaly_id, issue_type, ticket_id, entity_table, entity_id, rule_violated, field, injected_value, expected_value`. CSV and JSON have the same content. |
| 41 | Checksums | sha256 of every CSV, JSON and `seed.sql`. Not the `.db`. No wall-clock time in hashed files. |
| 42 | SQL dialect | SQLite DDL with PK, FK and CHECK. `seed.sql` via `iterdump()`. Validation runs with `PRAGMA foreign_keys=ON`. |
| 43 | JSON format | One records array per table, `sort_keys`, `indent=2`. |
| 44 | Starter scale | 1,000 tickets, 20 agents, 3,333 messages, 14 days, all 5 anomaly types present. |
| 45 | Tests | FAQ says optional; the spec asks for validation and repro. pytest provided anyway. |
| 46 | Prompt scope | Planning, workflow and subagent prompts included, scrubbed. |

---

## 3. Design critique

**Keep**
- One CLI, `--scale starter|full --seed 20261022`. Same code path for both.
- Hour × weekday seasonality, spikes, outage bursts, after-hours share.
- Eligibility = on shift, skill, language, below limit. Least-loaded, then longest-idle, then lowest ID.
- Language fallback with `translation_flag` is the mismatch scenario.
- Transfers, escalations and reopens driven by rules. Every step writes ASN rows.
- Business-time SLA on channel calendars.
- CSAT as a documented function plus small seeded noise, about 10 lines.
- Injection after the baseline, with separate ground truth.
- Precision and recall per type, computed as a set comparison only.
- README with ER diagram, `AI_USAGE.md`, `prompts/`.
- Tests for bizhours, routing eligibility, end-to-end and repro.

**Cut (overbuilt)**
- **Full DES with event classes, SHIFT_START, SLA_WARN and AGENT_FREE events.** Overbuilt. A heapq of routing requests plus busy-until slots is enough.
- **SLA `paused` and `warning` events.** Nothing in the spec needs them. Escalation replaces the warning.
- **Time-varying Poisson with λ(t)/thinning.** Doesn't give exactly 30k. Use `rng.choices(hours, weights, k=N)`.
- **numpy and pandas.** Not needed at 130k rows, and wheels for 3.15 are a risk.
- **YAML (and TOML).** Use `config.py`.
- **Makefile.** argparse subcommands are enough.
- **Separate detector modules.** The validators are the detectors.
- **Agent occupancy metric.** Fiddly denominator. Use peak concurrency vs limit.
- **Queue-wait histograms.** A p50/p90/p99 table is enough.

**Add (missing from the proposed design)**
- `docs/data_dictionary.md` plus a drift test (every `schema.sql` column must be in it).
- `docs/model.md`: Mermaid ER, cardinality, optional relationships, effective dates, lifecycle table.
- `manifest.json`: seed, scale, command, git SHA, config_hash, row counts, sha256, "external data: none (ISO 639-1 codes cited)".
- `validation_summary.md` written on every run.
- Arithmetic reconciliation checks and the duplicate check.
- Bridges `agent_skill`, `agent_language`, `queue_skill`. Effective dates.
- Pre-drawing every per-ticket random value before the loop, so there is no RNG inside routing.
- Repro test in two subprocesses with `PYTHONHASHSEED=1` and `=2`.
- Prompt capture from minute one.
- `expected_decisions.csv`.
- Capacity calibration: slots held for the working lifetime. Email limit about 6, chat 3, phone 1. Target 85–95% SLA attainment; the outage day breaches.

**Change**
- SLA engine becomes a pure post-pass. Routing only calls `sla.escalate_at()`.
- Escalation threshold: "SLA risk" becomes an exact 80% business-time point, which can be tested.
- Timezone: calendars in UTC, horizon Jan–Mar 2026, no DST.
- Python: `uv python pin 3.12`, stdlib only, pytest for dev.
- Commit `seed.sql` and CSVs for starter only. Full scale commits only `manifest.json`, `metrics.json` and `validation_summary.md`.

---

## 4. Final architecture

| Module | Responsibility |
|---|---|
| `__main__.py` | argparse: `generate --scale --seed --out`, `validate --dir`, `repro --scale` |
| `config.py` | Scales, channels, languages, intents (skill, default priority, `is_safety`), priority rules, SLA targets, calendars, holidays, shifts, limits, weights, spikes, anomaly counts |
| `ids.py` | ID formatters plus one regex per ID type |
| `bizhours.py` | `add_business_minutes`, `business_minutes_between`, `next_open`, `is_open` |
| `master.py` | Reference tables, customers, agents, bridges |
| `arrivals.py` | Ticket timestamps, channel, customer, intent, urgency, language, priority by rule, plus all per-ticket pre-draws |
| `routing.py` | heapq loop that emits ASN and Resolution rows |
| `sla.py` | Post-pass SLAEvents. `escalate_at()` is shared with routing. |
| `messages.py` | Threaded messages from the event timeline, exactly the target total |
| `outcomes.py` | CSAT and derived ticket columns |
| `anomalies.py` | 5 injectors `(tables, rng) -> gt_rows`, plus `expected_decisions` |
| `export.py` | CSV, JSON, SQLite load, `seed.sql`, manifest |
| `validate.py` | Structural and business-rule checks (SQL plus small Python), found vs ground truth |
| `report.py` | `metrics.json`, `validation_summary.md` |
| `schema.sql` | DDL with PK, FK and CHECK enums |

```
omnichannel-case-routing/
├── README.md               # problem, assumptions, decisions, trade-offs, install/run/verify, limitations, next steps
├── AI_USAGE.md             # tools, where AI drafted vs. you wrote, what you reviewed/changed/validated per module
├── pyproject.toml          # requires-python>=3.11, no runtime deps, dev: pytest
├── .python-version  uv.lock  .gitignore   # ignore data/full/csv, data/full/json, *.db, data/full/seed.sql
├── caserouting/
│   ├── __init__.py __main__.py config.py ids.py bizhours.py
│   ├── master.py arrivals.py routing.py sla.py messages.py outcomes.py
│   ├── anomalies.py export.py validate.py report.py
│   └── schema.sql
├── tests/
│   ├── test_bizhours.py    # edge-case table + round-trip property
│   ├── test_routing.py     # 3-agent fixtures: skill, lang fallback, capacity, shift
│   └── test_pipeline.py    # starter e2e: clean baseline 0 violations, found==GT per type, ID regex, escalation timing, dict drift, repro (2 subprocesses)
├── docs/
│   ├── data_dictionary.md
│   ├── model.md            # Mermaid ER, cardinality, optional rels, effective dates, lifecycle
│   └── REQUIREMENTS_TRACE.md
├── data/
│   ├── starter/            # committed in full
│   │   ├── csv/  json/  ground_truth/{ground_truth.csv,ground_truth.json,expected_decisions.csv}
│   │   └── seed.sql  manifest.json  metrics.json  validation_summary.md
│   └── full/               # commit manifest.json, metrics.json, validation_summary.md only
└── prompts/
    ├── README.md           # capture method, tools, gaps disclosed
    ├── 00_planning.md      # this planning session + workflow/subagent prompts
    ├── NN_<slice>.md
    └── raw/                # scrubbed transcript extracts
```

Run steps for the README:
- `uv sync`
- `uv run python -m caserouting generate --scale starter`
- `uv run python -m caserouting validate --dir data/starter`
- `uv run python -m caserouting repro --scale starter`
- `uv run pytest`

---

## 5. Key algorithms

**Routing loop (`routing.py`, about 150 lines, no RNG inside)**
- **Pre-draws per ticket (in `arrivals.py`):** handle_min, t2_handle_min, misroute flag and discover_min, reopen flag and delay, csat_noise, extra_msgs.
- **Heap:** `(ts, prio_rank, seq, ticket_id, reason)`, where reason is ARRIVAL, TRANSFER, ESCALATE or REOPEN. `seq` is a global counter.
- **Eligible agent:** on shift at `ts`, has the skill of the current queue, and speaks the language. After waiting `LANG_FALLBACK_MIN`, any language is allowed with `translation_flag=1`. Also `sum(t > ts for t in busy_until[a]) < limit`.
- **Pick:** `min((active/limit, last_free, agent_id))`. Candidate lists are sorted.
- **No eligible agent:** re-push at `min(earliest slot release or shift open among skill-eligible agents, escalate_at)`. If `escalate_at` comes first, write a queue-level ESCALATE row at that exact time.
- **On ASSIGN:** `end = ts + handle`, then:
  - If misrouted and `discover < handle`: TRANSFER at `ts + discover`, free the slot, push to the correct queue. A visited-queue set forbids revisits.
  - Else, if `end > escalate_at` and not yet escalated: ESCALATE at `escalate_at` and push to the T2 queue.
  - Else: RESOLVE at `end` and write a Resolution row. If reopen: push REOPEN at `end + delay`.
- **Shift rule:** new work only on shift; in-flight work finishes.
- **Limitation (documented):** priority only reorders requests competing at the same retry timestamp.

**SLA business time (`bizhours.py`, `sla.py`)**
- All times are integer minutes in UTC. Calendar format: `{weekday: [(start, end)]}` with end exclusive, plus a holidays set. 24x7 takes the fast path.
- `add_business_minutes` walks day by day, per open segment, with a guard of 400 days. A budget that equals the remaining open time means due at close. Arrival at close means the clock starts at the next open.
- `sla.py` post-pass:
  - `start = next_open(created)`
  - `fr_due = add(start, fr_target)`, `res_due = add(start, res_target)`
  - Met/breached is compared against first agent message and RESOLVE.
  - Reopen: `CLOCK_RESTARTED` with a new cycle; the target is restarted from the reopen time.
  - Open at horizon: breached if `due < horizon_end`, otherwise censored and excluded from the denominator.
- **Escalation proof:** every ESCALATE has `ts == escalate_at(ticket)`, and every unescalated ticket resolved before `escalate_at`.
- **Tests:**
  - Edge cases: after-hours, at close, at open, exact budget, Friday evening → Monday, Monday holiday, zero target, 24x7.
  - Round trip: `between(a, add(a, m)) == m`.

**Anomaly injection and detection (`anomalies.py`, detected by `validate.py`)**

General rules:
- Targets come from sorted, filtered candidate lists, drawn with the `anomalies` RNG, and are disjoint across types.
- Only the target ticket's rows are mutated. FKs stay valid. That ticket's derived columns are recomputed.

| issue_type | Candidate filter | Injection | Detector |
|---|---|---|---|
| CAPACITY_EXCEEDED | assigned and not escalated | ASSIGN `agent_id` set to agent B (same skill and language, at limit at `ts`). Rewrite later ASN, agent messages and `Resolution.agent_id`. | Per-agent sweep of `[assign, release)`, release before assign at equal ts (same rule as routing) |
| SLA_CALENDAR_IGNORED | business-hours channel, 24x7 due ≠ calendar due | Due = start + minutes; recompute that ticket's met/breach | Recompute with calendar, compare |
| REOPEN_HISTORY_LOST | reopened, not escalated | Delete pre-reopen ASN rows and cycle-1 Resolution; keep REOPEN and `reopen_count` | seq doesn't start at 001 or has a gap; REOPEN without a prior RESOLVE |
| TRANSFER_LOOP | resolved, at least one wait or handle gap | Insert queue-only TRANSFER rows A→B→A (agent null, so capacity is untouched) at increasing ts inside the window; renumber seq; update `transfer_count` | Queue revisited in the transfer path |
| PRIORITY_SAFETY_VIOLATION | `is_safety` intent, not escalated | priority = P3; recompute that ticket's SLA rows with P3 targets (consistent faulty output) | `intent.is_safety AND priority != 'P1'` |

- **Pass condition:** the baseline gives 0 business-rule findings. After injection, findings `{(issue_type, ticket_id)}` == ground truth. Structural checks still give 0 failures.
- **Precision and recall per type:** expected to be 1.0. State plainly that this is by construction (rule-based detectors), which proves the baseline is clean and injection is targeted.

**Reproducibility**
- `random.Random(f"{seed}:{stage}")` per stage: master, arrivals, predraw, messages, anomalies. Never use the global `random` or `hash()`.
- Never iterate a set; use `sorted()`. The heap has a `seq` tiebreak. Candidates are sorted by PK.
- Integers everywhere (minutes, CSAT). Floats written with `round(x, 4)`.
- Rows sorted by PK before export. CSV with `lineterminator="\n"`, utf-8. JSON with `sort_keys`, `indent=2`, trailing newline.
- No `now()` in hashed files. Manifest paths are relative. `generated_at` goes only in an unhashed `run_log.json`.
- Hash CSV, JSON and `seed.sql`, never the `.db`.
- `repro`: two subprocess runs with `PYTHONHASHSEED=1` and `2` into temp directories, then compare per-file counts and sha256. The result is written to `validation_summary.md`.

---

## 6. Hour-by-hour plan (America/Chicago)

**Every slice:** commit at the end with a real timestamp (no `--date`, no amending old commits). Write the prompts to `prompts/NN_<slice>.md` (tool, time range, verbatim prompts, scrubbed). Push at each checkpoint.

### Wed Nov 11

| Time | Slice | Done when / commit |
|---|---|---|
| 13:45–14:15 | **S0 Bootstrap:** `git init`, `gh repo create omnichannel-case-routing --public`, `uv python pin 3.12`, pyproject (pytest dev), `.gitignore`, CLI stub, `prompts/00_planning.md` (this session plus all workflow and subagent prompts) | `python -m caserouting --help` works. `chore: bootstrap skeleton and CLI`. **Save prompts.** |
| 14:15–15:45 | **S1** `config.py`, `ids.py`, `bizhours.py`, `test_bizhours.py` | Edge and round-trip tests green. `feat: config, ID formats, business-hours calendar math`. **Save prompts.** |
| 15:45–16:00 | Break | |
| 16:00–17:30 | **S2** `schema.sql`, `master.py`, minimal `export.py` (CSV + SQLite load + `foreign_key_check`) | Master CSVs load with 0 FK errors. `feat: schema DDL and master/bridge data`. **Save prompts.** |
| 17:30–19:00 | **S3** `arrivals.py`: hourly weights, spikes, outage, after-hours, priority rule, pre-draws | Exact N tickets, after-hours share printed. `feat: arrivals with seasonality, spikes, priority rules`. **Save prompts.** |
| 19:00–20:00 | Dinner | |
| 20:00–22:30 | **S4** `routing.py` v1 (assign, resolve, capacity, language fallback, shifts), `test_routing.py` | Starter runs end to end to CSV. `feat: heapq routing respecting skill, language, shift, capacity`. **Save prompts.** |
| 22:30–23:00 | **Checkpoint A:** push; next task in `NOTES.md` | Starter runs end to end with 0 PK/FK errors |

Checkpoint A fallback:
- S4 incomplete: Thursday starts with S4, apply cut items 1–3.
- S2 incomplete: also apply cut item 4.

### Thu Nov 12

| Time | Slice | Done when / commit |
|---|---|---|
| 07:30–09:30 | **S5** routing lifecycle: misroute transfers, escalation at `escalate_at`, reopens, queue-level escalate | Lifecycle chains are legal. `feat: transfers, escalations, reopens`. **Save prompts.** |
| 09:30–11:00 | **S6** `sla.py` post-pass, `messages.py` (exact total), `outcomes.py` (CSAT, derived columns) | Message total = target. `feat: SLA post-pass, threaded messages, CSAT and derived columns`. **Save prompts.** |
| 11:00–11:15 | Break | |
| 11:15–13:00 | **S7** `validate.py`: PK, FK, enum, regex, date order, lifecycle, duplicates, reconciliation, capacity sweep, eligibility, history, SLA recompute, escalation timing | **Checkpoint B (13:00):** starter baseline has 0 violations. `feat: validators`. **Save prompts.** |
| 13:00–14:00 | Lunch | |
| 14:00–16:30 | **S8** `anomalies.py`: 5 injectors, `ground_truth.csv`/`.json`, `expected_decisions.csv`; found==GT test | Test green per type. `feat: labelled anomaly injection with separate ground truth`. **Save prompts.** |
| 16:30–16:45 | Break | |
| 16:45–18:30 | **S9** export finish: JSON, `seed.sql`, manifest with sha256, `repro` command and subprocess test | Repro identical. `feat: CSV/JSON/SQL export, manifest, reproducibility check`. **Save prompts.** |
| 18:30–19:30 | Dinner | |
| 19:30–21:00 | **S10** full run plus calibration: SLA 85–95%, outage day breaches, runtime under 2 min, exact 30k/100/100k/90d | Full run validates. `feat: full-scale run and calibration`. **Save prompts.** |
| 21:00–22:15 | **S11** `report.py`: SLA by channel × priority, skill and language match, translation rate, transfer, escalation and reopen rates, wait p50/p90/p99, peak concurrency vs limit, mixes, CSAT distribution, precision/recall | `feat: metrics report and validation summary`. **Save prompts.** |
| 22:15–22:30 | **Checkpoint C:** `git tag v1 && git push --tags`; gap list in `NOTES.md` | S8, S9 and S10 done |

Checkpoint B fallback:
- Routing not producing tickets: reopen becomes a plain new routing request, escalation becomes queue-level only, apply cut items 1–4.

Checkpoint C fallback:
- S11 missing: move it to Fri 07:30.
- S8 or S9 missing: apply cuts down to item 7.

### Fri Nov 13

| Time | Slice | Done when / commit |
|---|---|---|
| 07:30–09:00 | **H1** `docs/REQUIREMENTS_TRACE.md`: section 1 rows mapped to file, test or metric; fix gaps | `docs: requirements traceability; fix gaps`. **Save prompts.** |
| 09:00–12:00 | **H2** `data_dictionary.md` + drift test, `model.md` (ER, cardinality, effective dates, lifecycle), README (all GL-04 items, env, timings), `AI_USAGE.md`, provenance note ("no external data") | `docs: README, data dictionary, model, AI usage`. **Save prompts.** |
| 12:00–13:00 | Lunch | |
| 13:00–14:30 | **H3** clarity pass: types, comments, `ponytail:` notes, remove dead code; rehearse routing, bizhours, injectors | `refactor: clarity pass for walkthrough`. **Save prompts.** |
| 14:30–15:30 | **H4** finalize `prompts/`: export transcripts, extract every prompt including workflow and subagent ones, scrub secrets and `/Users/` paths, disclose gaps | `docs: complete prompt history`. |
| 15:30–16:30 | **H5** fresh-clone run in a temp directory: `uv sync`, generate, validate, repro, pytest | **Checkpoint D:** green means feature freeze. Fix only clone breakages. |
| 16:30–20:00 | Buffer, dinner, walkthrough rehearsal | |
| 20:00–21:00 | **Final checklist** (below) | `docs: submission notes`. **Save final prompts.** |
| 21:00–22:00 | **Checkpoint E:** submit from the recruitment email; screenshot the confirmation | Done by 22:00. |
| After | No risky pushes. Typo-only fixes before 03:00 Sat. Repo stays public. | |

**Final checklist**
1. Trace matrix has no gaps. Every edge case appears in ground truth. The 4 acceptance criteria are covered by named tests.
2. Fresh clone passes pytest and repro on the final commit.
3. Incognito check: repo is public and the README renders. `prompts/`, `docs/` and `data/starter/` are visible.
4. `git grep -iE 'key|token|password|secret|@gmail|/Users/'` is clean.
5. `git log --format='%ci %s'` shows every commit between Wed 03:41 and Sat 03:41.
6. No file is over 50MB.
7. `AI_USAGE.md` and `prompts/README.md` disclose all tools and any gaps.

**Cut list (drop in this order)**
1. PriorityRule day-45 version change (keep the effective-date columns)
2. Mermaid pipeline diagram (keep the ER diagram)
3. Longest-idle tiebreak
4. Message channel differing from ticket channel
5. CSAT noise (deterministic formula only)
6. Holidays (weekends and hours only; document it)
7. `expected_decisions.csv` (anomaly ground truth only)
8. Full-scale JSON export (CSV, `seed.sql` and manifest only)

**Never cut:**
- 5 labelled anomaly types with found==GT
- PK/FK and lifecycle validation
- Seed and the repro check
- bizhours and routing tests
- README run and verify steps, `prompts/`, `AI_USAGE.md`

---

## 7. Top risks

1. **Bizhours bugs** (after-hours, at-close, holidays). These break SLA reproducibility and escalation timing. Mitigation: walk by day and segment, never minute by minute; edge-case table plus round-trip property test, written first (Wed).
2. **Injection side effects**, so findings ≠ ground truth. Mitigation: disjoint, filtered candidates (not escalated, etc.); queue-only transfer-loop rows; recompute only the target ticket; found==GT test per type.
3. **Hidden nondeterminism** (set order, heap ties, `now()`). Mitigation: sorted iteration, `seq` tiebreak, per-stage string-seeded RNGs, subprocess repro with different `PYTHONHASHSEED` values.
4. **Calibration.** Too much capacity gives no queueing or breaches; too little gives runaway queues. Mitigation: slots held for working lifetime, spikes capped at 4h, metrics printed after every run from Thu 19:30, target 85–95% attainment.
5. **Capacity tie rule mismatch** between routing (`busy_until > now`) and the validator sweep. Mitigation: release before assign at equal ts in both; one shared comment and one fixture test.
6. **Schedule.** Routing plus lifecycle is the critical path. Mitigation: Checkpoint B fallbacks and the cut list.
7. **Prompt history incomplete** (workflow and subagent prompts). Mitigation: save at every slice end, H4 sweep, disclose gaps.
8. **Commit timestamps and repo size.** Mitigation: real-time commits only; full-scale CSV, JSON and `.db` gitignored, manifest checksums committed.