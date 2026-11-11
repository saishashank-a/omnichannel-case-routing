# Completeness critic on PLAN.md

**(1) Missing or under-specified requirements**
- **SLA/message circular dependency:** The generation order is ASN → SLAEvent → Message, yet SLA first-response met/breached is checked against the "first agent message". The exact-total trim in `messages.py` could also delete that message. Fix: take first-response time from routing (ASSIGN ts plus a pre-draw), have `messages.py` place the agent message at that time, and forbid trimming it.
- **Cross-format ID consistency (PS-Gen-3):** No check confirms that IDs match across CSV, JSON and SQL. Add one test that compares the PK sets for each table across the three exports.
- **Shift coverage vs the 24x7 P1 calendar:** The plan doesn't say whether any agents work nights or Sundays. If none do, every overnight P1 and outage ticket breaches and the 85–95% calibration fails. Define the shifts (e.g. `SHF-NIGHT`) and minimum staffing per skill × language × shift, including for the 20-agent starter.
- **Tier-2 and Sales staffing:** No agent attribute or skill (e.g. `SKL-T2`, `SKL-SALES`) says who serves the T2 and `QUE-SALES` queues. Without it, escalated and prospect tickets can starve.
- **Escalation per cycle:** After a reopen, it isn't stated whether `escalate_at` is recomputed from `CLOCK_RESTARTED`, or whether T2 tickets can escalate again. The escalation-timing test needs this defined.
- **`sla_id`:** It's a column with no parent table. Either add a 1:1 `sla` header table (PK `SLA-TKT-…`, which satisfies PS-IDs literally) or document `sla_id` as a non-FK grouping key.
- **CSAT `wait_penalty`:** The formula is undefined. Also, the LANG_FALLBACK_MIN, misroute discover k and reopen p values aren't listed anywhere. They should be in `config.py` and the data dictionary.
- **Duplicate check (PS-Gen-8):** The non-PK natural key is undefined, e.g. customer + created_at + channel for tickets, ticket + ts + author for messages. Date-ordering pairs aren't listed either.
- **`expected_decisions` output:** It is CSV only, while PS-Gen-7 asks for csv/json. Either add the JSON or state the deviation.
- **History vs snapshot columns:** Ticket columns such as status, current queue/agent and counts must be documented as derived from events. Otherwise they read as overwriting history (PS-Workflow-4).
- **Full-scale data isn't committed:** The README must give the exact full regenerate command, the expected sha256 values from the manifest, the runtime, and the note that `uv` needs network access to fetch 3.12 (the system Python is 3.15).
- **Message threading:** The threading field isn't specified (`seq` only, or `in_reply_to`). State which one and how it's validated.

**(2) Internal inconsistencies**
- **Transfer vs escalation order:** The ASSIGN branch checks misroute first. If `discover > escalate_at`, the ticket transfers after `escalate_at` without escalating. That breaks the "every unescalated ticket resolved before `escalate_at`" proof. Use `min(discover, escalate_at, end)`.
- **Proof wording vs code:** The code escalates when `end > escalate_at`, so the proof should say "resolved at or before `escalate_at`".
- **Queue-level ESCALATE vs lifecycle:** It fires from QUEUED, but lifecycle #32 only allows ASSIGNED→ESCALATED. Add QUEUED→ESCALATED.
- **CLOSED state:** It appears in the lifecycle, but no ASN event type or rule produces it. Either drop it or define a CLOSE rule (e.g. resolved and no reopen within N days).
- **TRANSFER_LOOP rows:** Inserting them in a "handle gap" puts a TRANSFER on an ASSIGNED ticket without a QUEUED step, so the lifecycle validator flags it. "Structural checks still give 0 failures" then fails. Restrict insertion to queued-wait gaps.
- **CAPACITY_EXCEEDED side effects:** Agent B may be off shift during later rewritten events. The sweep also flags the overload interval, which involves several tickets. The filter needs B on shift for the whole interval, and attribution should go to the ticket whose ASSIGN crossed the limit. Restrict candidates to single ASSIGN→RESOLVE tickets so the rewrite is one row pair.
- **PRIORITY_SAFETY_VIOLATION:** Moving to P3 also changes the calendar from 24x7 to the channel calendar. "Recompute with P3 targets" must say which calendar, or the SLA recompute or SLA_CALENDAR_IGNORED detector double-fires.
- **SLA_CALENDAR_IGNORED start time:** "start + minutes" doesn't say whether start is `created` or `next_open`. Use `created`, so after-hours arrivals are actually affected.
- **Hashing scope:** "Hash every JSON" would include `manifest.json`, which contains its own checksums and the git SHA. It would also include `run_log.json`. Exclude both, and say whether `metrics.json` is hashed.
- **Generation order:** Assumption 1 puts Resolution after Message, but `routing.py` emits Resolution rows.
- **ID padding:** `RES-…-01` is 2-digit while everything else is 3-digit. Use `-001`.
- **Missing from the tree:** `NOTES.md` and `run_log.json`.
- **Unclear Checkpoint B trigger:** "routing not producing tickets" should be stated as a measurable condition, e.g. lifecycle validator red at 13:00.

**(3) Still overbuilt for 72h with one human explaining every line**
- **PRL day-45 version change:** Drop it now rather than waiting for the cut list. Keep the columns.
- **`translation_flag` fallback timer:** A wait timer plus per-language staffing is a second retry axis. A simpler option is fallback only when no language match exists among skill-eligible agents.
- **Precision/recall per type:** It's 1.0 by construction and adds nothing beyond the found==GT set equality. Report found==GT only.
- **TRANSFER_LOOP seq renumbering and CAPACITY_EXCEEDED rewrites:** These are the hardest lines to explain. Append loop rows only on wait-only tickets, and restrict capacity candidates as above.
- **`REQUIREMENTS_TRACE.md` with 186 rows (1.5h):** Group it by source section (about 25 rows).
- **`PYTHONHASHSEED` 1/2 subprocess repro:** Reasonable, but one subprocess pair is enough. Don't also keep an in-process variant.
- **Queue-level ESCALATE plus slot-release retry plus shift-open retry:** Three retry sources. Consider a fixed retry tick (e.g. 5 min) plus `escalate_at`, documented as a limitation.