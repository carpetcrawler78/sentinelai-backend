# Claude Code Prompt — GitHub Synchronization Rules

**Author:** ChatGPT 5.5 Thinking  
**Date:** 2026-06-12  
**Project:** job-search-system  
**Prompt type:** Claude Code execution prompt  
**Purpose:** Update project governance files so GitHub becomes the coordination source of truth, with `PROJECT_MEMORY.md` as the single source of truth for rules/planning and append-only status logs for ChatGPT and Claude/Fable/Opus.

---

## Context

This repository is:

```text
carpetcrawler78/job-search-system
```

Current agreed model:

```text
ChatGPT = Master planner / reviewer / strategist / prompt and document designer
Claude Fable / Opus = second master for planning/review/strategy
Claude Code = execution-side slave/worker for both masters
```

Important role boundary:

ChatGPT must not execute code or perform operative implementation. Claude Code performs file operations, pull/commit/push, and implementation tasks.

---

## Mandatory start procedure for Claude Code

Before changing anything:

1. Run `git status`.
2. Run `git pull`.
3. Read these files:
   - `PROJECT_MEMORY.md`
   - `status-chatgpt.md`
   - `status-claude.md` if it exists
4. If `status-claude.md` does not exist, create it as an append-only log file.
5. Check for discrepancies between:
   - `PROJECT_MEMORY.md`
   - `status-chatgpt.md`
   - `status-claude.md`
6. Report discrepancies in your response before making substantive changes.

---

## Task 1 — Ensure `status-claude.md` exists

If missing, create:

```text
status-claude.md
```

Initial content:

```markdown
# Claude/Fable/Opus Status — job-search-system

This file is an append-only chronological handoff log for Claude Code / Fable / Opus sessions.

## Rules

- Preserve all previous entries.
- Add new dated session updates at the bottom.
- Do not rewrite older entries except to fix obvious formatting errors with explicit note.
- At the start of every Claude/Fable/Opus session, read `PROJECT_MEMORY.md`, `status-chatgpt.md`, and this file.
- Report discrepancies against `PROJECT_MEMORY.md` before continuing.

---

## Session update — 2026-06-12 — file initialized

### Change made

Initialized `status-claude.md` as the append-only handoff log for Claude Code / Fable / Opus sessions.

### Current role model

- ChatGPT = master planner / reviewer / strategist / prompt and document designer.
- Claude Fable / Opus = second master for planning, review and strategy.
- Claude Code = execution-side worker/slave for both masters.

### Current source-of-truth model

- `PROJECT_MEMORY.md` = single source of truth for standing rules, current planning and execution coordination.
- `status-chatgpt.md` = append-only ChatGPT session log.
- `status-claude.md` = append-only Claude/Fable/Opus session log.
```

---

## Task 2 — Add GitHub synchronization section to `PROJECT_MEMORY.md`

Append or insert a new section named:

```markdown
## GitHub synchronization model
```

Use this content, preserving all existing content:

```markdown
## GitHub synchronization model

GitHub is the coordination and versioning source for project rules, planning files, prompts and status logs.

`PROJECT_MEMORY.md` is the single source of truth for standing rules, latest planning decisions and execution coordination.

Google Drive remains the source of truth for final exported artifacts and deliberately stored project documents.

### Agent access model

- ChatGPT reads and writes the remote GitHub repository through its GitHub connector.
- Claude Fable / Opus may work from a local clone and therefore may see only the last pulled state.
- Claude Code is the execution-side worker that performs local filesystem changes, `git pull`, commits and `git push`.

### Pull / push discipline

At the start of every Claude Code execution session:

1. Run `git status`.
2. Run `git pull`.
3. Read `PROJECT_MEMORY.md`, `status-chatgpt.md` and `status-claude.md`.
4. Check for discrepancies and report them before continuing.

At the end of every Claude Code execution session:

1. Append a dated update to `status-claude.md`.
2. Run `git status`.
3. Commit intentional changes with a clear commit message.
4. Push to GitHub.
5. Report the commit hash and changed files.

### Write boundaries

- ChatGPT appends to `status-chatgpt.md`.
- Claude Fable / Opus / Claude Code appends to `status-claude.md`.
- `PROJECT_MEMORY.md` may be changed only for agreed global rules, source-of-truth definitions, role boundaries or workflow changes.
- `PROJECT_MEMORY.md` edits should be small, explicit and easy to review.
- If a status file conflicts with `PROJECT_MEMORY.md`, `PROJECT_MEMORY.md` wins.

### Conflict prevention

Avoid parallel edits to the same file.

Preferred split:

- ChatGPT: planning, review, prompts, `status-chatgpt.md`, proposed memory changes.
- Claude Fable / Opus: planning/review notes, `status-claude.md`, proposed memory changes.
- Claude Code: execution of file operations, commits, pushes, and implementation tasks requested by either master.
```

---

## Task 3 — Append status update to `status-claude.md`

After making the changes, append a new dated entry to `status-claude.md`:

```markdown
---

## Session update — 2026-06-12 — GitHub synchronization rules added

### Change made

Added/confirmed GitHub synchronization rules for the multi-agent setup.

### Rules confirmed

- GitHub is the coordination and versioning source for planning, prompts, rules and status logs.
- `PROJECT_MEMORY.md` is the single source of truth for standing rules and latest planning/execution coordination.
- Google Drive remains the source of truth for final exported artifacts and deliberately stored project documents.
- Claude Code must `git pull` at the start and `git push` at the end of execution sessions.
- All status files are append-only.

### Discrepancies found

Document any discrepancies found during this session here.

### Files changed

List changed files here.
```

---

## Acceptance criteria

- `status-claude.md` exists.
- `PROJECT_MEMORY.md` contains a `GitHub synchronization model` section.
- `status-claude.md` contains an append-only dated update for this task.
- Existing status entries in `status-chatgpt.md` are preserved.
- No existing status history is deleted.
- Claude Code reports changed files and commit hash after push.

---

## Do not

- Do not overwrite `status-chatgpt.md`.
- Do not delete older status entries.
- Do not rewrite project strategy beyond the synchronization rules above.
- Do not change CV strategy files in this task.
