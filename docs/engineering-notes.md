# Engineering Notes

A curated selection of architecture decisions and debugging stories from
the project's development diary (`DEVLOG.md`, full chronological log, not
included here). This is an excerpt for readers who want the engineering
substance without the day-to-day session noise -- not a replacement for
the full log.

---

## The `localhost` fallback bug (Docker networking)

**Symptom:** 82.9% of all coded records (4,740 of 5,832) carried a
hardcoded fallback value (`llm_confidence = 0.3`) instead of a real LLM
output.

**Root cause:** `OLLAMA_DEFAULT_URL` was hardcoded to
`http://localhost:11434`. Inside a Docker container, `localhost` resolves
to the container itself, not to the sibling Ollama container -- so every
LLM call failed silently and fell back to a default confidence value.

**Fix:** Read the Ollama URL from an environment variable instead of a
hardcoded default. Introduced a `VIGILEX_STRICT` flag so failures raise
immediately in development (fail-fast) instead of silently degrading to a
fallback value (fail-soft) that is easy to miss in production-style runs.
Affected records were backed up, truncated, and re-coded.

**Lesson:** A pipeline that fails soft by default hides its own failure
rate. Fail-fast in development, and make any fail-soft path in production
emit a metric that is impossible to ignore.

---

## Sentinel-value fallback bug (second occurrence)

**Symptom:** After a 12-hour worker run, a statistical check of the
confidence-value distribution showed 68% of records at exactly
`llm_confidence = 0.50` and 22% at exactly `0.80`, with **zero** records in
the 0.5-0.7 range -- a real, continuous LLM output would not cluster on
two exact values with a gap between them.

**Root cause:** A second, independent hardcoded sentinel/default value path
in the coding logic, distinct from the one fixed above.

**Lesson:** Distribution shape is a cheap and effective bug detector.
Before trusting an aggregate metric (mean, recall, accuracy), plot the
underlying value distribution and look for suspiciously exact clusters --
real model output rarely lands on round numbers.

---

## Multi-worker conflict and a "zombie" ingest process

**Symptom:** All Ollama calls started failing with HTTP 500 after exactly
60 seconds, starting at a specific time. Several hours of container-log
debugging did not find the cause.

**Root cause:** Simple host-level diagnostics (`uptime`, `top`) -- tried
only after the container-log route was exhausted -- immediately showed CPU
load at 9.5 on a 4-vCPU host. Two independent causes stacked: a "zombie"
ingest process left running by a `docker compose run -d` race condition,
plus a second coding worker running in parallel (one via host `tmux`, one
via Docker) against the same queue.

**Lesson:** Check host-level resource metrics before diving into
application logs -- a resource-starvation symptom (timeouts, 500s) can
look identical to an application bug and cost hours of the wrong kind of
debugging. Enforce a single-instance policy for any worker that polls a
shared queue; running the same worker twice (host + container) is a race
condition waiting to happen.

---

## pg_trgm retrieval bugs (hybrid search pipeline)

A cluster of small but instructive bugs surfaced while building the hybrid
BM25/vector retrieval stage:

- **`similarity()` vs. `word_similarity()`:** using the wrong pg_trgm
  function returned zero matches even for an exact text match present in
  the corpus -- `similarity()` compares whole strings, `word_similarity()`
  compares against the best-matching word/phrase inside a longer string.
- **Trigram case sensitivity:** trigram matching is case-sensitive by
  default; un-normalized casing between the query and the indexed column
  silently dropped otherwise-correct matches.
- **Embedding dilution on long narratives:** mean-pooling an embedding
  over a long free-text narrative diluted the signal from the clinically
  relevant sentence. Fix: embed only the first sentence of the narrative
  rather than the full text.

**Lesson:** Each of these produced a plausible-looking but wrong result
(not a crash) -- the kind of bug that only shows up when you check
individual retrieval results against expectation, not just aggregate
recall.

---

## Cross-repository push accident

**Mistake:** An unrelated session (working on a different, unrelated
project) pushed nine commits into this repository's `main` branch, because
the wrong git remote was active in that session's shell.

**Fix:** Reverted cleanly via a revert commit; no content was lost.

**Rule:** Before working across multiple projects in the same terminal
session, check the active repository and remote explicitly
(`git remote -v`) rather than assuming it from the working directory name.

---

## Git sync across two machines

**Symptom:** Repeated `! [rejected] (fetch first)` push errors when
developing from two machines (a remote dev server and a local machine)
against the same branch.

**Fix:** `git pull --rebase origin <branch>` before every push, automated
via a scheduled job on both sides rather than relying on remembering to do
it manually.

**Lesson:** Two independent write locations on one branch will eventually
race; rebase-before-push (and automating that habit) is cheaper than
resolving the conflict after the fact.
