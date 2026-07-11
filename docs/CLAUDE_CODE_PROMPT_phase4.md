# Claude Code Prompt -- Phase 4: Query Fusion Implementation

Lies zuerst:
- vigilex/CLAUDE.md (Current Truth)
- data/eval/DECISION.md (Entscheidung: mpnet + Query Fusion)
- docs/evaluation/embedding_benchmark_2026-05-26.md (Bench-Ergebnisse)

Dann folgende Schritte in dieser Reihenfolge -- STOP nach jedem Schritt und zeig mir das Ergebnis.

---

## Schritt 0 -- Status-quo-Baseline (5 min, Hetzner)

ssh cap@46.225.109.99
cd ~/vigilex && python scripts/baseline_vector_only.py
cat data/eval/status_quo_baseline.json

Zeig mir R@1 / R@5 / R@100 fuer PubMedBERT vector-only.
Wenn status_quo_baseline.py nicht existiert: zeig mir eval_golden_set.py
und wir bauen es gemeinsam.

---

## Schritt 1 -- Git-Konflikt loesen (Hetzner)

ssh cap@46.225.109.99
cd ~/vigilex && git status

Zeig mir die Ausgabe. Dann gemeinsam den Konflikt loesen (git add -A, commit, push).

---

## Schritt 2 -- Schema-Migration (zeigen, nicht ausfuehren)

Erstelle: migrations/004_embedding_mpnet.sql

Inhalt (zeig mir SQL vor Ausfuehrung):
ALTER TABLE processed.meddra_terms
    ADD COLUMN IF NOT EXISTS embedding_mpnet vector(768);

Noch NICHT ausfuehren. Erst review.

---

## Schritt 3 -- embed_meddra_terms_v2.py (lokal entwickeln, dann push)

Erstelle: scripts/embed_meddra_terms_v2.py

Das Skript soll:
- SentenceTransformer("all-mpnet-base-v2") laden
- processed.meddra_terms lesen (pt_code, pt_name, pt_concept_code)
- Pool-Representation: nur pt_name (pt_only)
- Embeddings in Batches von 64 berechnen
- In embedding_mpnet Spalte schreiben (UPDATE)
- Progress logging
- Idempotent (ueberspringt bereits befuellte Zeilen falls moeglich)

ASCII only im Code. Zeig mir das Skript vor git push.

---

## Schritt 4 -- hybrid_search.py: Query Fusion

Lies zuerst: hybrid_search.py vollstaendig.

Aendere Stage-1 Vector-Retrieval so:
- Encoder: all-mpnet-base-v2 (statt PubMedBERT)
- Index-Spalte: embedding_mpnet (statt bestehende Embedding-Spalte)
- Zwei Queries parallel:
    q1 = first_sentence(mdr_text)
    q2 = mdr_text[:512]
    c1 = vector_search(embed(q1), top_k=50)
    c2 = vector_search(embed(q2), top_k=50)
    candidates = dedupe_by_pt_code(c1 + c2)
- BM25-Arm: unveraendert
- CrossEncoder + LLM: unveraendert

Zeig mir nur den geaenderten Abschnitt (diff-artig), nicht die ganze Datei.

---

## Schritt 5 -- Re-Embedding auf Hetzner (tmux, background)

Nachdem Schritt 2+3 reviewed und gemergt:

ssh cap@46.225.109.99
cd ~/vigilex && git pull origin work
tmux new -s reembed
python scripts/embed_meddra_terms_v2.py 2>&1 | tee data/eval/reembed.log
# Ctrl+B d zum Detach -- laeuft im Hintergrund (~10-30 min)

---

## Schritt 6 -- pgvector Index nach Re-Embedding

Nach Abschluss von Schritt 5:

psql -d vigilex -c "
CREATE INDEX IF NOT EXISTS idx_meddra_mpnet_ivfflat
ON processed.meddra_terms
USING ivfflat (embedding_mpnet vector_cosine_ops)
WITH (lists = 100);
"

---

## Schritt 7 -- Eval nach Migration

python scripts/eval_golden_set.py
# oder baseline_vector_only.py mit neuer Embedding-Spalte

Erwartetes Ergebnis: R@100 >= 0.65 (Bench-Wert war 0.667 auf mismatched Index).
Wenn schlechter: melden, nicht weitermachen.

---

## Was bewusst NICHT geaendert wird

- CrossEncoder-Modell
- LLM-Coding-Step
- BM25-Arm
- pt_only Pool-Definition
- clinical_window (V2)
- RRF-Gewichtung (V2)
