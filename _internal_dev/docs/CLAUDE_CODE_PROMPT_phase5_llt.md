# Claude Code Prompt -- Phase 5: Tests + Qwen-Eval
# (Stand 2026-05-26 Abend -- LLT-Expansion abgeschlossen und reverted)

Lies zuerst:
- CLAUDE.md (Current Truth, im Repo-Root)
- vigilex/CLAUDE.md (Code-Details, Schema, Worker-Topologie)
- data/eval/DECISION.md (Phase 4+5 abgeschlossen, Eval-Ergebnisse)

---

## Aktueller Stand (2026-05-26, Abend)

Phase 4 DONE:
- all-mpnet-base-v2 + Query Fusion aktiv in hybrid_search.py
- 27361 Embeddings in processed.meddra_terms.embedding_mpnet
- IVFFlat Index idx_meddra_mpnet_ivfflat aktiv
- Eval-Pipeline: eval_golden_set.py mit MLflow, soft_recall, category breakdown

Eval-Ergebnisse Stage 1+2 (top_k_stage1=20, eingefroren):
- recall_at_5=0.333 | soft_recall_at_5=0.500
- recall_at_10=0.500 | soft_recall_at_10=0.833
- p_at_1=0.083 | mrr=0.191 | R@100=0.750
- cat_A=11 | cat_B=5 | cat_hit=8

LLT-Expansion: EXPERIMENT ABGESCHLOSSEN, REVERTED
- Index gebaut, LLT-Arm getestet: kein Verbesserung (cat_A 11->12)
- Erklaerung: Vocabulary-Gap ist Query-Problem, nicht Index-Problem
- Reverted in hybrid_search.py, dokumentiert in data/eval/DECISION.md

Tests:
- tests/conftest.py: FERTIG
- tests/test_reranker.py: FERTIG (8 Tests, CE gemockt vor Instanziierung)
- tests/test_api.py: IN PROGRESS

---

## ABGESCHLOSSEN (nicht nochmal ausfuehren)

- Schritt 1-5 (LLT-Index, LLT-Arm, Eval, Doku, stale Label): DONE

---

## Schritt 6 -- test_api.py fertigstellen (IN PROGRESS)

Lies zuerst: src/vigilex/api/main.py vollstaendig.
Pruefe dabei: sind limit und offset tatsaechlich die letzten zwei
SQL-Parameter? (test_list_pagination baut darauf auf -- falls nicht, Index anpassen)

Strategie:
- autouse=True auf set_env Fixture -- API_KEY in jedem Test via os.environ
- mock_db Fixture: patch('vigilex.api.main.get_connection') + get_cursor
- TestClient aus starlette.testclient (httpx Dependency:
  pip install httpx --break-system-packages)

12 Tests:

| Test | Was geprueft |
|---|---|
| test_health_ok | GET /health -> 200, status="ok", kein Key benoetigt |
| test_health_db_error | DB-Fehler gemockt -> 200, db enthaelt "error:" |
| test_list_requires_auth | ohne Key -> 401 |
| test_list_wrong_key | falscher Key -> 401 |
| test_list_ok | gueltiger Key, gemockte Zeilen -> 200, Liste |
| test_list_pagination | limit/offset als params[-2]/params[-1] ans SQL |
| test_list_filter_min_confidence | min_confidence=0.5 in SQL-Bedingung |
| test_list_exclude_fallback | exclude_fallback=True -> IS DISTINCT FROM 0.3 |
| test_stats_ok | GET /coding-results/stats -> 200, CodingStats Felder |
| test_get_by_id_ok | GET /coding-results/1 -> 200, CodingResult |
| test_get_by_id_not_found | GET /coding-results/99999 -> 404 |
| test_get_by_id_db_error | Exception direkt auf get_connection -> 500 |

ASCII only. Zeig mir test_api.py komplett vor dem Schreiben. STOP.

---

## Schritt 7 -- pytest ausfuehren

```bash
cd ~/vigilex
python3 -m pytest tests/test_reranker.py tests/test_api.py -v
```

Erwartet: alle 20 Tests gruen (8 reranker + 12 api).
Bei Fehlern: Ausgabe zeigen, gemeinsam fixen.
Dann: GitHub Actions CI/CD pruefen.

---

## Schritt 8 -- Qwen-Vergleich (wenn pytest gruen)

Pruefen ob qwen2.5:7b auf Ollama verfuegbar:
```bash
docker exec vigilex-ollama ollama list
# Falls nicht da: docker exec vigilex-ollama ollama pull qwen2.5:7b
```

Dann Eval-Run:
```bash
cd ~/vigilex
set -a && source .env && set +a
python3 scripts/eval_golden_set.py \
    --stage3-model qwen2.5:7b \
    --run-name qwen25_7b
```

Ergebnis: p_at_1_llm fuer qwen2.5:7b in MLflow.
Zum Vergleich llama3.2:3b Run starten:
```bash
python3 scripts/eval_golden_set.py \
    --stage3-model llama3.2:3b \
    --run-name llama32_3b
```

MLflow Vergleich: beide Runs nebeneinander -> Tabelle fuer Talk #3.
STOP nach beiden Runs. Zahlen zeigen.

---

## Was bewusst NICHT geaendert wird

- CrossEncoder-Modell (cross-encoder/ms-marco-MiniLM-L-6-v2)
- LLM-Coding-Step (llama3.2:3b)
- BM25-Arm (pg_trgm, lower()/ILIKE)
- RRF-Gewichtung (w_bm25=0.4, w_vec=0.6)
- top_k_stage1=20 (top_k=50 Experiment war schlechter)
- Golden Set (24 Cases, frozen)
- LLT-Arm (reverted, Future Work)

---

## Critical Rules (nicht vergessen)

- KEIN FAISS -> pgvector IVFFlat
- "ranking index" bei Stakeholdern, NIE "confidence score"
- Single-Instance-Policy: NIE Host-Worker (tmux) + Docker-Worker gleichzeitig
- ASCII only in Code-Files
- Schema nie raten: mdr_text (NICHT event_description), coded_at (NICHT created_at)
- Groq: nur Benchmarking, NIE Production
