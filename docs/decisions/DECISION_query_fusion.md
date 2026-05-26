# Architecture Decision: Query Fusion for Stage-1 Retrieval

**Date:** 2026-05-26
**Status:** Accepted -- Phase 4 implementation
**Related:** data/eval/DECISION.md, docs/evaluation/embedding_benchmark_2026-05-26.md

---

## Decision

Use Query Fusion (always parallel, no threshold) as Stage-1 retrieval strategy.
Run first_sentence and full_text_truncated queries in parallel, union candidates,
pass to CrossEncoder. Same model (mpnet), same index, same reranker throughout.

## Rejected Alternative

Adaptive two-pass with CE_THRESHOLD / GAP_THRESHOLD trigger.
Rejected because: confidently wrong retrieval produces high CE score and large gap --
trigger never fires. Failure is silent and unrecoverable in a medical coding context.

## Scope for Capstone

Query strategies: first_sentence + full_text_truncated only.
clinical_window, AE-phrase extraction, RRF weighting: deferred to V2.

## Talk Framing

"The benchmark showed that first-sentence queries give better top-rank precision,
while full-text queries recover additional correct candidates at deeper ranks.
SentinelAI therefore runs both queries in parallel -- the CrossEncoder then selects
from the combined candidate pool. This avoids the failure mode of threshold-based
adaptive retrieval, where a confident wrong retrieval suppresses the second pass."
