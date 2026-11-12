# Prompt history

Every prompt sent to an AI tool during this challenge, in order. AI responses are not included (optional per the FAQ).

| # | File | Tool | Summary |
|---|------|------|---------|
| 001 | [001-kickoff.md](001-kickoff.md) | Claude Code (Opus 5.5) | Brief, proposed design, working agreement |
| 002 | [002-problem-statement.md](002-problem-statement.md) | Claude Code (Opus 5.5) | Pasted the authoritative problem statement |
| 003 | [003-create-repo.md](003-create-repo.md) | Claude Code (Opus 5.5) | Create repo, save prompts |
| 004 | [004-prompts-in-dev.md](004-prompts-in-dev.md) | Claude Code (Opus 5.5) | Keep prompts folder under ~/dev |
| 005 | [005-show-plan.md](005-show-plan.md) | Claude Code (Opus 5.5) | Show plan when workflow finishes |
| 006 | [006-build-today-and-explain.md](006-build-today-and-explain.md) | Claude Code (Opus 5.5) | Compressed schedule; plain-language explanation |
| 007 | [007-metrics-source.md](007-metrics-source.md) | Claude Code (Opus 5.5) | Are metrics specified by the problem? |
| 008 | [008-assessment-type.md](008-assessment-type.md) | Claude Code (Opus 5.5) | What is being assessed? |
| 009 | [009-ui-prompt-request.md](009-ui-prompt-request.md) | Claude Code (Opus 5.5) | Ask for a UI prompt to hand to Codex/Gemini |
| 010 | [010-ui-prompt-in-chat.md](010-ui-prompt-in-chat.md) | Claude Code (Opus 5.5) | Show UI prompt in chat |
| 011 | [011-codex-model.md](011-codex-model.md) | Claude Code (Opus 5.5) | Which Codex model for the UI |
| 012 | [012-codex-version.md](012-codex-version.md) | Claude Code (Opus 5.5) | Codex version correction |
| 013 | [013-rewrite-ui-prompt.md](013-rewrite-ui-prompt.md) | Claude Code (Opus 5.5) | Rewrite UI prompt for Codex |
| 014 | [014-launch-codex.md](014-launch-codex.md) | Claude Code (Opus 5.5) | How to launch Codex |
| 015 | [015-work-in-parallel.md](015-work-in-parallel.md) | Claude Code (Opus 5.5) | Work in parallel (treated as go) |
| 016 | [016-run-ui-starter.md](016-run-ui-starter.md) | Claude Code (Opus 5.5) | Run the viewer on real starter data (found UTC timestamp bug) |
| 017 | [017-remaining-gaps.md](017-remaining-gaps.md) | Claude Code (Opus 5.5) | List remaining tasks and gaps |
| 018 | [018-do-items.md](018-do-items.md) | Claude Code (Opus 5.5) | Do the submission checklist (Claude did 2-4; 1 and 5 left to me) |

## Agent-generated prompts

Claude Code sometimes delegates work to sub-agents, writing their prompts itself. Those prompts were not typed by me, but they were sent to an AI model, so they are kept in [`agent-generated/`](agent-generated/) for completeness.

| File | Spawned by | Purpose |
|------|-----------|---------|
| [agent-generated/001-planning-workflow.js](agent-generated/001-planning-workflow.js) | prompt 001 | 4 parallel planning lenses (requirements, design critique, technical risk, schedule) → synthesis → completeness critic |
| [agent-generated/002-bizhours-agent.md](agent-generated/002-bizhours-agent.md) | prompt 015 | Business-hours maths + tests (parallel agent) |
| [agent-generated/003-schema-docs-agent.md](agent-generated/003-schema-docs-agent.md) | prompt 015 | schema.sql, data dictionary, model docs (parallel agent) |

## Conventions

- One file per prompt: `NNN-short-slug.md`, with tool, approximate send time (America/Chicago) and purpose at the top.
- Prompts are copied verbatim.

## Prompts sent to other tools

Prompts I sent to Codex CLI or Gemini CLI. Each file records which tool and model received it.

| File | Purpose |
|------|---------|
| [codex/001-ui-viewer.md](codex/001-ui-viewer.md) | Read-only results viewer in `ui/` (drafted by Claude Code, sent verbatim) |
| [codex/002-summary-for-claude.md](codex/002-summary-for-claude.md) | Asked Codex for a summary of its finished work to paste into Claude Code |
