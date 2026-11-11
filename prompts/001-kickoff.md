# 001 — Kickoff brief

- **Tool:** Claude Code (CLI), model Claude Opus 5.5
- **Sent:** 2026-11-11 ~13:30 CST (Chicago)
- **Purpose:** project brief, design proposal, working agreement
- **Note:** the message also invoked several planning slash-commands (listed at the end). The three attachments it refers to were not attached; the PDFs were read from disk, and the problem statement was sent as the next prompt (002).

---

You are my senior pair-engineer for a timed take-home. Goal: a complete, working, documented v1 by Thursday Nov 12 night (Chicago time), with Friday for hardening, docs and submission.

CONTEXT
- Company: YottaFlex AI (Hyderabad). Role: AI Forward Deployed Engineer. Round 3: 72-hour individual code challenge.
- HARD DEADLINE: Sat Nov 14, 3:11 PM IST = Sat Nov 14, 3:41 AM Chicago. I'm in Chicago. My real target is Friday 10 PM Chicago. The repo version at the deadline is what gets evaluated.
- Attached: the problem statement (.txt), the Submission Guidelines PDF and the FAQ PDF. Read all three before planning.

WHAT THE GUIDELINES REQUIRE
1. Working, executable code, with clear steps to install, configure, run and verify key behaviour.
2. A new, dedicated public GitHub repo. Meaningful commits that show how the work evolved (timestamps are used to verify the window).
3. PROMPT HISTORY IS REQUIRED: every prompt sent to every AI tool, kept in a clearly named folder (prompts/). Plus an AI_USAGE.md explaining where AI sped things up, where I relied on it heavily, and what I personally reviewed, changed or validated.
4. Visible reasoning: problem understanding, assumptions, key decisions, trade-offs, testing approach, limitations, and how I know it works.
5. Individual work. AI is allowed; help from other people is not. No importing existing code that does the core work. Free or locally runnable services only, and no heavy or slow dependencies.
6. A partial solution is acceptable if what works, what doesn't, the limitations and the next steps are stated honestly.
7. No secrets or personal data in the repo. All data is synthetic.
I must be able to explain every line in a later walkthrough, so keep the code plain, typed and commented where a decision isn't obvious.

THE PROBLEM (summary; the attached .txt is authoritative)
Omnichannel support case routing: route email, chat and phone cases by intent, urgency, language, skill and agent capacity while tracking SLA. Build a synthetic-data generator plus a routing/SLA engine that exposes decisions and exceptions, keeps full traceability, and produces measurable outputs.
- Entities: Customer, Channel, Ticket, Message, Intent, Language, PriorityRule, Agent, Skill, Queue, AssignmentEvent, SLAEvent, Resolution. A PK on every entity, FKs on every relationship, bridge tables for N:M (agent_skill, agent_language), documented cardinality, effective dates and lifecycle states. State changes are append-only events; never overwrite history.
- IDs: TKT-2026-000001, MSG-<ticket-id>-001, AGT-000001, ASN-<ticket-id>-001, SLA-<ticket-id>. Zero-padded, immutable, consistent across files.
- Volume: 30,000 tickets, 100 agents, 100,000 messages, 90 days of events. Fixed seed 20261022, with a scale parameter so the starter and full datasets come from the same generator.
- Required scenarios: language mismatch, critical incidents, queue spikes, after-hours arrivals.
- Business logic: threaded messages across channels; an intent/priority taxonomy; SLA calendars per channel; agent skills, languages, shifts and concurrency limits; assignment; transfers, escalations and reopenings; resolution and CSAT.
- Generate valid baseline data first, then inject labelled anomalies: agent assigned beyond capacity, SLA ignores channel calendar, reopened ticket loses history, transfer loop, priority contradicts a safety rule. Label them in a separate ground_truth.json/csv that never leaks into input features, and don't corrupt unrelated rows.
- Derived values (statuses, SLA due times, breaches, durations, CSAT) are computed from source records and documented rules, never randomly assigned on their own.
- Validation: PK uniqueness, FK integrity, enums, date ordering, arithmetic reconciliation, lifecycle transitions, duplicates.
- Export CSV + JSON + a SQL seed, a README, a schema/data dictionary (type, required, allowed values, units, uniqueness, validation rule per field), the generator command, the seed, a source manifest and a validation summary.
- Reproducibility: generate twice with the same seed and compare row counts and SHA-256 checksums.
- Acceptance: routing respects skill and capacity; SLA is reproducible; escalation timing is correct; assignment history is complete.

MY PROPOSED DESIGN (challenge it)
- Python 3.11, numpy + pandas, SQLite for the SQL seed, pytest, a YAML config. One CLI: `python -m caserouting generate --scale starter|full --seed 20261022 --out data/`. A Makefile with: setup, starter, full, validate, test, repro.
- config/: channels, languages, intent taxonomy with default priority, priority/safety rules (e.g. a safety or outage intent can never be below P1), SLA policies per priority x channel (first response + resolution), channel calendars (phone/chat with business-hour shifts, email business days only, plus holidays), queues.
- Arrivals: time-varying Poisson with hour-of-day and weekday seasonality, injected spike windows and after-hours share. Customers have a preferred language.
- Routing as a discrete-event simulation over 90 days: arrival -> intent/priority classification by documented rule -> queue -> pick an eligible agent (on shift, has the skill, speaks the language, below concurrency limit), choosing least utilised and then longest idle -> otherwise wait in queue. Language fallback with a translation flag counts as the mismatch scenario. Transfers when skill is missing, escalation when SLA risk crosses a threshold, reopen probability by rule. Every step writes AssignmentEvent/SLAEvent rows.
- SLA engine: due times computed in business time on the channel calendar; events for started, paused, warning, met and breached.
- CSAT is a documented function of breach, transfers, reopens and wait time, plus a seeded small noise term.
- Anomaly injector runs after the baseline and writes ground_truth with issue_type, entity IDs and the rule violated.
- Validators and anomaly detectors re-check the data independently. Report: detector precision/recall against ground truth, SLA attainment by channel and priority, skill/language match rate, agent occupancy, transfer and escalation rates, queue wait distributions.
- Tests: unit tests for the SLA calendar maths, routing eligibility, ID formats and each anomaly type, plus an end-to-end test on the starter scale and a reproducibility test.

HOW I WANT TO WORK
1. First reply: a requirements checklist covering every line of the .txt and the PDFs, ambiguities with the assumption you'd make for each, your critique of my design, the repo structure, and an hour-by-hour plan to Thursday night Chicago. Wait for my OK before coding.
2. Build in vertical slices, with the starter scale (~1,000 tickets) running end to end early. Then scale up and check runtime (target: the full dataset in a few minutes on a laptop).
3. Commit after every slice with clear messages. Remind me to save prompts into prompts/ as we go.
4. README: problem in my own words, a Mermaid ER diagram and pipeline diagram, quickstart from a fresh clone, design decisions and trade-offs, how verification works, metrics output, limitations, next steps.
5. Friday: re-check against the checklist, fresh-clone run, the repro check, an incognito check of the public link, then submit through the portal (same email I used during recruitment).

Be direct and tell me if anything is overbuilt for the time I have.

---

Slash-commands appended to the same message:

```
/everything-claude-code:plan /compound-engineering:ce:plan /oh-my-claudecode:plan /ponytail:ponytail /superpowers:brainstorm /superpowers:write-plan ultracode
```
