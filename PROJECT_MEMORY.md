# Project Memory — job-search-system

This file is the single source of truth for standing project instructions, current planning rules and execution coordination.

## Mandatory startup rule

At the start of every ChatGPT session that works on the `job-search-system` project, read these three files before making plans, editing project files or discussing next steps:

1. `PROJECT_MEMORY.md`
2. `status-chatgpt.md`
3. `status-claude.md`

After reading them, immediately check for discrepancies between the three files and report any discrepancy to the user before continuing.

If a status file is missing, report that as a discrepancy.

## File roles

### PROJECT_MEMORY.md

`PROJECT_MEMORY.md` is the single source of truth for:

- standing project rules
- current planning decisions
- execution coordination rules
- source-of-truth definitions
- role boundaries between master LLMs and execution agents
- latest agreed project workflow

If `PROJECT_MEMORY.md` conflicts with a status file, `PROJECT_MEMORY.md` wins.

### status-chatgpt.md

`status-chatgpt.md` is an append-only chronological handoff log for ChatGPT sessions.

It should preserve prior entries and add new dated entries at the bottom.

### status-claude.md

`status-claude.md` is an append-only chronological handoff log for Claude Code / Fable / Opus sessions.

It should preserve prior entries and add new dated entries at the bottom.

## Source of truth for project files

Google Drive folder:

`Projekte_Drive/job-search-system`

is the source of truth for the **job-search-system project**.

Important clarification:

- This Drive folder is the source of truth for the project structure, project-level working documents, final project exports and status handoff material.
- It is **not automatically** the source of truth for all CVs, Enhancv exports, historical application documents or certificates.
- Existing CVs and application materials in other Drive locations remain source material and may be used as input when explicitly selected.
- A CV or export becomes project-level source material only when it is deliberately copied/linked into the project workflow or documented in the repository.

## GitHub role

GitHub repository:

`carpetcrawler78/job-search-system`

is the versioned working repository for Markdown files, prompts, tracker templates, scoring rules, CV strategy drafts, cover-letter templates and project memory.

## Assistant role boundary

ChatGPT's role in this project is **discussion, planning, analysis, review and text/prompt drafting only**.

ChatGPT must **not** execute code, run local scripts, run terminal commands, perform implementation work, or act as the operative coding/execution agent for this project.

Operational execution belongs to Claude Code / Fable / Opus or another explicitly designated execution tool/agent.

Working model:

- ChatGPT = master planner / reviewer / strategist / prompt and document designer.
- Claude Code / Fable / Opus = execution-side master for code, filesystem implementation, scripts and operative changes.

If implementation is needed, ChatGPT should provide:

- exact plan
- acceptance criteria
- file-by-file instructions
- prompts for Claude Code / Fable / Opus
- review checklist

but should not itself execute code.

## Status handoff rule

At the end of every working session on the `job-search-system` project, append a new dated entry to the relevant status file.

- ChatGPT sessions append to `status-chatgpt.md`.
- Claude Code / Fable / Opus sessions append to `status-claude.md`.

Append-only rule: preserve all earlier status entries and add each new session update at the bottom of the file.

The appended update should summarize:

- current project state
- files changed or created
- strategic decisions made
- open tasks
- next recommended steps
- any important caveats or source-of-truth clarifications
- discrepancies found between project memory and status files, if any

## Strategic job-search rule

The project should avoid positioning Thomas Heger primarily as a classic operational Clinical Data Manager.

Clinical Data Management is used as domain proof, not as the target identity.

Target direction:

- Health AI / Clinical AI
- Healthcare Data Science
- Clinical Data Engineering
- Healthcare AI / Clinical Data Consulting

Avoid prioritizing:

- public-sector E9/E10 classic CDM roles
- medical documentation only
- query resolution only
- EDC maintenance only
- low-development operational CDM positions
