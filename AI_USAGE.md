# AI usage

AI was allowed for this challenge, and I used it heavily. This file covers which tools I used, what
each one did, where I leaned on it, and what I checked myself. Every prompt is in
[`prompts/`](prompts/), in order.

## Tools

| Tool | Model | Used for |
|---|---|---|
| Claude Code (CLI) | Claude Opus 5.5 | Planning, all Python code in `caserouting/`, tests, docs, commits |
| Claude Code sub-agents | Claude Opus 5.5 | Planning workflow (4 lenses + synthesis + critic); `bizhours.py` + tests; `schema.sql` + data dictionary + model doc. Their prompts are in `prompts/agent-generated/` |
| Codex CLI 0.163.0 | gpt-6-luna (medium effort) | The optional read-only viewer in `ui/`. Prompt in `prompts/codex/` |

## Where AI accelerated the work

- **Planning.** A multi-agent planning pass produced the requirements checklist (186 items), the
  ambiguity list and a design critique in about 8 minutes
  ([`docs/PLAN.md`](docs/PLAN.md), [`docs/PLAN_CRITIC.md`](docs/PLAN_CRITIC.md)). It pushed my
  original design toward something simpler: no pandas, no YAML, no full discrete-event engine.
- **Boilerplate-heavy parts.** The DDL with CHECK constraints, the 18-table data dictionary, the
  CSV/JSON/SQL exporters and the business-hours edge-case tests were drafted by AI.
- **Running in parallel.** The business-hours maths and the schema docs were written by sub-agents
  while the main session wrote config, master data and routing. The UI was built by Codex in
  parallel, against a data contract written up front.

## Where I relied on it heavily

- The routing simulation (`routing.py`) and the anomaly injectors (`anomalies.py`) were written by
  Claude from the agreed design. These are the most complex parts, so they are also where my
  review was most important (below).
- The UI is entirely Codex output. It is optional and not part of the core deliverable.

## Bugs and changes caught during the build (in the commit history)

| What happened | How it was caught | Fix |
|---|---|---|
| The first SLA attainment check reported 0% met | Numbers looked impossible; the check script used `x and 0 or 1`, which is always 1 | Fixed the analysis script (the data was fine) |
| 5 structural "duplicate" failures after injection | Validation summary | Transfer-loop rows repeat a queue at the same minute; the duplicate key now includes `reason` |
| 1 of 30 capacity anomalies missed at full scale | Detection table showed `missed 1` | The injector's busy-slot map went stale after it moved tickets between agents; it now updates the map and never moves work off an agent it overloaded |
| P2–P4 met 100% of SLAs and 90% of tickets waited 0 min | Reading the metrics | Calibrated handle times and concurrency limits (commit `900a8cc`) |
| The viewer timeline showed browser-local time (a 00:17Z ticket appeared as 18:17 the day before) while ticket fields showed UTC | Running the Codex-built viewer on the real starter data, not its sample | Timeline formats timestamps in UTC (commit `8ee3ac3`) |

## Checks run by Claude Code at my request (2026-11-12)

These were run by Claude, not by me. They are listed separately so the section below stays accurate.

- **Ticket 1 SLA by hand:** created Thu 2026-01-01 00:17Z (a holiday), EMAIL P3. The clock starts Fri
  08:00, so first response is due 08:00 + 240 = 12:00, and resolution (1200 business minutes) is due
  Fri 600 + Mon 600 = Mon 2026-01-05 18:00. Both match `data/starter/csv/sla.csv`.
- **P1 24x7 clock:** all 99 starter P1 tickets have resolution due = created + 480 minutes.
- **Escalation at 80%:** 26 of 27 P1 escalations fire at created + 384 minutes. The 27th
  (`TKT-2026-000723`) was reopened and escalated at reopen + 384 minutes, which is the documented
  rule that a reopen starts a new SLA cycle (`docs/model.md`). The script's assumption was wrong,
  not the data.
- **Tests and reproducibility:** `pytest` 61 passed; a fresh starter regeneration matched every
  checksum in the committed `manifest.json`; `repro` reported identical output across two runs.
- **Viewer on real data:** found that the timeline showed browser-local time; fixed (commit `8ee3ac3`).

## What I directed

My role was direction, not hand-coding. Every instruction is in [`prompts/`](prompts/).

- **The design.** The kickoff ([prompt 001](prompts/001-kickoff.md)) set out the approach:
  - a clean baseline first, with labelled anomalies injected after it
  - ground truth kept separate from the input tables
  - validators that double as the anomaly detectors
  - the ID formats, and statuses and other derived values computed from source records rather than
    randomly assigned
  - the reproducibility check and the test plan

  I asked Claude to challenge that design. I accepted its push toward something simpler (standard
  library only, no pandas or YAML).
- **Scope and schedule.** I compressed the plan to a single day, with five checkpoints and cut rules
  ([prompt 006](prompts/006-build-today-and-explain.md)). I required vertical slices, code simple
  enough to explain line by line, and prompts saved as we went.
- **Tool choice.** I chose to build the optional viewer in parallel with Codex CLI, picked its model
  from Claude's suggestion, and launched it myself ([prompts 009–015](prompts/), [`prompts/codex/`](prompts/codex/)).
- **Verification.** I had the viewer run on the real data instead of Codex's sample, which caught
  the time-zone bug. I also had the checks above run (prompts 016 and 020), and asked for the
  results to be recorded as Claude's, not mine.
- **Honesty of this record.** When the Codex session log showed a different CLI version from the one
  I had given, I kept the logged version in this file and my original message unchanged in
  [prompt 012](prompts/012-codex-version.md).

The hands-on checks (running tests, comparing checksums, working out SLA due times by hand) were
carried out by Claude Code at my direction, as listed in the section above. I did not run them
myself.

## Limitations of this record

- Prompts typed into Claude Code and Codex are saved verbatim. Sub-agent prompts were extracted from
  the session transcripts.
- AI responses are not included; the FAQ says they are optional.
