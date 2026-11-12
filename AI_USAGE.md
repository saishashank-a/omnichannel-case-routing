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

## What I personally reviewed, changed or validated

> **TODO (me):** fill this in honestly before submitting. For example: which modules I read line
> by line, which numbers I checked by hand (one ticket's SLA due time against the calendar), which
> design choices I overrode, what I ran from a fresh clone. Do not list anything I did not do.

-
-
-

## Limitations of this record

- Prompts typed into Claude Code and Codex are saved verbatim. Sub-agent prompts were extracted from
  the session transcripts.
- AI responses are not included; the FAQ says they are optional.
