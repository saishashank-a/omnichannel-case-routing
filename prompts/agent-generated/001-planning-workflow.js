export const meta = {
  name: 'takehome-plan',
  description: 'Plan YottaFlex case-routing take-home: requirements, design critique, risk, schedule, then critic',
  phases: [
    { title: 'Analyze', detail: '4 independent lenses' },
    { title: 'Synthesize', detail: 'merge into one plan' },
    { title: 'Critique', detail: 'completeness critic vs source text' },
  ],
}

const CTX = `
=== PROBLEM STATEMENT (authoritative) ===
${args.problem}

=== SUBMISSION GUIDELINES + FAQ (authoritative) ===
${args.guidelines}

=== CANDIDATE'S PROPOSED DESIGN ===
${args.design}

=== TIMING / ENV ===
${args.timing}
`

const LENSES = [
  { key: 'requirements', prompt: `You are a meticulous requirements analyst. Using ONLY the sources below, produce an exhaustive numbered requirements checklist: every sentence of the problem statement, guidelines and FAQ that implies a deliverable or constraint becomes one checkbox line, tagged with its source (PS-<section>, GL-0x, FAQ-x). Include the Evaluation Focus items (a)-(g), Primary Actors, Public Data Guidance, the 'before you submit' list. Then list every AMBIGUITY you find (e.g. 'Ticket/Message listed as master data', '100k messages vs 30k tickets ratio', 'SLA-<ticket-id> implies one SLA id per ticket but SLAEvent is many per ticket', 'MSG-<ticket-id>-001 makes IDs long', 'what counts as escalation timing correct', 'what Language/Skill/Queue/PriorityRule PKs look like since no format given', 'expected decisions in ground truth', 'agent shifts timezone', 'actors like marketing/sales ops and sysadmin') each with ONE concrete recommended assumption. Be exhaustive; terse lines.` },
  { key: 'critique', prompt: `You are a blunt senior engineer reviewing a 72-hour take-home design for over/under-building. The candidate must explain every line in a walkthrough and wants to finish v1 by Thursday night. Critique the proposed design against the problem statement: what is overbuilt (cut it), what is missing vs the spec (add it), what is risky. Specifically judge: full discrete-event simulation vs simpler event-driven loop; SLA pause/warning events; time-varying Poisson; YAML config vs Python constants; SQLite seed vs plain .sql text; detector precision/recall; CSAT model; pandas necessity; Makefile. Propose the simplest architecture that still satisfies every acceptance criterion (routing respects skill/capacity; SLA reproducible; escalation timing correct; assignment history complete) and the evaluation focus (a)-(g). Give a concrete module list (file names, one-line responsibility each) and a concrete repo tree including prompts/ and AI_USAGE.md. Also specify ID formats for entities with no given format. Be direct.` },
  { key: 'risk', prompt: `You are a technical-risk reviewer focused on correctness and performance of the core algorithms. For the routing simulation over 90 days with 30k tickets, 100 agents, 100k messages: (1) design the event loop concretely (heap of events? minute-tick? per-ticket greedy with agent busy-until lists?) and estimate runtime in pure Python; recommend the simplest approach that runs full scale in < 2 min. (2) Business-time SLA math on channel calendars with holidays: give a correct, simple algorithm (e.g. walking calendar intervals) and its edge cases (arrival after hours, deadline spanning weekend/holiday, DST — recommend a single fixed timezone to avoid DST). (3) Reproducibility pitfalls that break SHA-256 equality (dict/set ordering, float formatting, pandas version, timestamps in manifest, datetime.now, parallelism) and how to neutralize each. (4) How to inject each of the 5 anomalies without corrupting unrelated rows and keep derived values consistent, and how an independent detector finds each. (5) What tests give most confidence per hour spent. Concrete, terse.` },
  { key: 'schedule', prompt: `You are a delivery planner. Build an hour-by-hour plan in America/Chicago time from NOW (Wed Nov 11 ~14:00 CST) to v1 complete Thursday Nov 12 night, then Friday hardening/docs/submission, with the user's real target Fri 22:00 CST and hard deadline Sat 03:41 CST. Assume a human with realistic sleep (~7h/night) and meals, pairing with an AI coding agent. Work in vertical slices with starter scale (~1000 tickets) running end-to-end EARLY (by Wed night). Each slice ends with a commit (give the commit message) and a reminder to save prompts into prompts/. Include buffer, and an explicit cut list (what to drop, in order) if behind schedule at named checkpoints. Include Friday checklist: re-check requirements, fresh-clone run, repro check, incognito check of public repo, submit via portal from recruitment email. Note: commit timestamps must fall inside window (started Wed 03:41 CST).` },
]

phase('Analyze')
const results = await parallel(LENSES.map(l => () =>
  agent(`${l.prompt}\n\n${CTX}`, { label: `lens:${l.key}`, phase: 'Analyze' }).then(r => ({ key: l.key, r }))))
const got = results.filter(Boolean)
log(`lenses returned: ${got.map(g => g.key).join(', ')}`)

phase('Synthesize')
const plan = await agent(`Merge these independent analyses into ONE planning document for the candidate, in markdown, terse and direct (no fluff). Sections in this order:
1. Requirements checklist (every line, source-tagged, checkboxes) — complete, do not drop items.
2. Ambiguities -> assumption (table).
3. Design critique: Keep / Cut / Add / Change, with one-line reasons. Call out overbuilt items bluntly.
4. Final architecture: module list + repo tree.
5. Key algorithms (routing loop, SLA business-time, anomaly injection+detection, reproducibility) — brief.
6. Hour-by-hour plan (Chicago) with slice commits, prompt-save reminders, checkpoints and cut list.
7. Top risks.
Resolve conflicts between analyses by choosing the simpler option that still meets acceptance criteria; note the choice.

${got.map(g => `=== ${g.key.toUpperCase()} ===\n${g.r}`).join('\n\n')}

${CTX}`, { label: 'synthesize', phase: 'Synthesize' })

phase('Critique')
const critic = await agent(`You are a completeness critic. Compare the PLAN below against the SOURCE texts line by line. List (1) any requirement in the sources missing or under-specified in the plan, (2) any internal inconsistency in the plan (times, IDs, module names), (3) any item still overbuilt for 72h with a single human who must explain every line. Terse bullet list only; if nothing, say so.

=== PLAN ===
${plan}

${CTX}`, { label: 'critic', phase: 'Critique' })

return { plan, critic }
