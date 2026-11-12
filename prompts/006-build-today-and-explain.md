# 006 — Build today; explain in simple words

- **Tool:** Claude Code (CLI), model Claude Opus 5.5
- **Sent:** 2026-11-12 ~08:20 CST (Chicago)
- **Purpose:** compressed schedule (finish Thursday), checkpoints, rules; asked for a plain-language explanation

---

Let's start building now. Goal: the COMPLETE submission done today. Deadline is in IST; I'm working from Chicago.

- NOW: Thu Nov 12, 8:20 AM Chicago = Thu Nov 12, 7:50 PM IST
- HARD DEADLINE: Sat Nov 14, 3:11 PM IST = Sat Nov 14, 3:41 AM Chicago
- MY TARGET: everything finished and submitted by Thu Nov 12, 11:00 PM Chicago = Fri Nov 13, 10:30 AM IST
  (Friday is buffer only: fixes, no new features.)

TODAY'S CHECKPOINTS
- 11:30 AM Chicago (11:00 PM IST): repo + config + master data (Customer, Channel, Intent, Language, Skill, Queue, PriorityRule, Agent with skill/language bridges, shifts). First commit pushed.
- 2:30 PM Chicago (2:00 AM IST): tickets + threaded messages + routing/SLA simulation (assignment, transfers, escalations, reopenings, resolution, CSAT) working end to end at starter scale.
- 5:00 PM Chicago (4:30 AM IST): anomaly injection + separate ground_truth, validators (PK, FK, enums, date order, lifecycle, reconciliation, duplicates), CSV/JSON/SQL exports + manifest with checksums. v1 pushed and link submitted on the portal.
- 8:00 PM Chicago (7:30 AM IST): full scale (30k tickets, 100k messages, 100 agents, 90 days) runs in reasonable time, metrics report, reproducibility check (two runs, same checksums), pytest suite.
- 11:00 PM Chicago (10:30 AM IST): README, data dictionary, ER + pipeline diagrams, AI_USAGE.md, prompts/ folder, validation summary. Fresh-clone test and private-window link check. DONE.

RULES
1. Skip the long planning: a short requirements checklist + repo structure, then straight into code.
2. Build in vertical slices and keep the starter scale runnable at every checkpoint.
3. At each checkpoint, tell me where we stand in both IST and Chicago. If we're behind, propose what to cut so the core acceptance criteria still ship (routing respects skill/capacity, SLA reproducible, escalation timing correct, assignment history complete).
4. Remind me to commit after each slice and to save my prompts into prompts/.
5. Keep the code simple enough that I can explain every line.

can you tell me in simple words what are we building?
