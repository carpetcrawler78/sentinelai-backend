# SentinelAI -- Evaluation Plan (Post-Midterm)

**Stand 2026-05-26. Zuletzt aktualisiert: Phase-4 Golden Set Ergebnisse eingetragen.**
*(Original erstellt 2026-05-21 im Rahmen Friday Talk #2 / Midterm-Prep.)*

Dieses Dokument beschreibt den Eval-Plan fuer die zweite Haelfte des Capstones
(22. Mai bis 3. Juni). Hauptziel: messbare Qualitaet ohne Expert-Labels via
LLM-as-judge, plus Vorbereitung der Datengrundlage fuer Expert-Labels nach
Capstone-Ende.

---

## Aktueller Eval-Stand (2026-05-26)

Golden Set (`data/eval/golden_set_v1.jsonl`, 24 Cases) + Eval-Pipeline vollstaendig.
Ergebnisse Stage 1+2 (top_k_stage1=20, top_k_stage2=5):

| Metrik | Wert | Bedeutung |
|---|---|---|
| recall_at_5 (strict) | 0.333 | expected PT in Stage-2 top-5 |
| soft_recall_at_5 | 0.500 | + acceptable_pt_codes |
| recall_at_10 (strict) | 0.500 | expected PT in Stage-1 top-10 |
| soft_recall_at_10 | 0.833 | + acceptable_pt_codes |
| p_at_1_reranker | 0.208 | top-1 Stage-2 == expected PT |
| mrr | 0.257 | Mean Reciprocal Rank in Stage-2 top-5 |
| R@100 Stage-1 | 0.750 | candidate recall ceiling |

Bottleneck-Breakdown (Category-Analyse):

- **Cat A** (Stage-1 miss, ~6 Cases): expected PT nicht im 100er-Pool -- Ursache: Vocabulary-Gap
  (numerische BG-Werte, Geraete-Sprache statt AE-Term). LLT-Expansion adressiert dieses.
- **Cat B** (CrossEncoder dropped, ~4 Cases): Stage-1 findet es, CrossEncoder verwirft.
  Groesserer Pool (top_k=50) hilft NICHT -- macht es schlechter (Experiment 2026-05-26).
- **Cat C/hit** (~14 Cases): im Pool, davon ~8 in top-5.

Soft Recall: acceptable_pt_codes fuer 8 Cases definiert (case-spezifisch, nicht universell).
Soft R@5 = 0.500 zeigt dass 12/24 Cases zumindest einen klinisch defensiblen PT in top-5 haben.

---

## Warum dieser Plan jetzt

Beim Midterm habe ich folgende Tatsachen kommuniziert:
- 11,161 Records codiert ueber 3 Devices (LZG / OYC / QFG)
- Fuer Pre-19.05-Records (10,656) gibt es kein explizites `llm_status`-Logging,
  Real-LLM-vs-Fallback ist nur heuristisch (`llm_confidence` IN (0.30, 0.50, 0.80))
- Fuer Post-19.05-Records (505 QFG) gibt es sauberes Status-Logging
- Bisher kein Quality-Measure ausser der Fallback-Rate (und die nur fuer
  neue Records sauber)

Strict accuracy (recall@5) braucht expert-labeled Reference-Set -- das ist
"Beyond Capstone". Was wir bis 3. Juni leisten koennen: LLM-as-judge auf den
505 neuen Records aufsetzen, plus die Infrastruktur fuer spaetere Expert-Labels
vorbereiten.

---

## Phase 1: Echte Cases fuer Demo + Eval finden

Vor LLM-as-judge brauchen wir saubere Case-Samples. Drei Buckets, jeweils
SQL-getrieben.

### 1a -- Echte Easy Cases (Term steht im Text)

Records wo der vom System gewaehlte `pt_name` wortwoertlich in der Narrative vorkommt.
Das ist der einfache Fall, wo pg_trgm-Arm direkten Match findet.

```sql
SELECT
  cr.id,
  cr.mdr_report_key,
  cr.pt_name,
  cr.final_confidence,
  cr.crossencoder_score,
  LEFT(mdr.mdr_text, 400) AS narrative_excerpt
FROM processed.coding_results cr
JOIN raw.maude_reports mdr USING (mdr_report_key)
WHERE cr.llm_status = 'success'                  -- nur Post-19.05 mit sauberem Logging
  AND cr.final_confidence > 0.75
  AND mdr.mdr_text ILIKE '%' || cr.pt_name || '%'   -- term IS in text
ORDER BY cr.final_confidence DESC
LIMIT 20;
```

### 1b -- Echte Hard Cases (Term NICHT im Text, hohe Confidence)

Der spannendste Fall: das LLM bekommt durch semantisches Reasoning trotzdem
hohe Confidence, obwohl der MedDRA-Term lexikalisch nicht in der Narrative auftaucht.
Genau das was wir auf der Mid-Term-Demo-Folie als "HARD Case" zeigen wollten.

```sql
SELECT
  cr.id,
  cr.mdr_report_key,
  cr.pt_name,
  cr.final_confidence,
  cr.crossencoder_score,
  cr.rationale,
  LEFT(mdr.mdr_text, 400) AS narrative_excerpt
FROM processed.coding_results cr
JOIN raw.maude_reports mdr USING (mdr_report_key)
WHERE cr.llm_status = 'success'
  AND cr.final_confidence > 0.75
  AND mdr.mdr_text NOT ILIKE '%' || cr.pt_name || '%'   -- term NOT in text
ORDER BY cr.final_confidence DESC
LIMIT 20;
```

### 1c -- Echte "I don't know" Cases (low ranking)

Low-ranking Records wo das System selbst Unsicherheit signalisiert.
Diese Buckets bilden zusammen die Test-Suite.

```sql
SELECT
  cr.id,
  cr.mdr_report_key,
  cr.pt_name,
  cr.final_confidence,
  cr.crossencoder_score,
  cr.rationale,
  LEFT(mdr.mdr_text, 400) AS narrative_excerpt
FROM processed.coding_results cr
JOIN raw.maude_reports mdr USING (mdr_report_key)
WHERE cr.llm_status = 'success'
  AND cr.final_confidence < 0.35
ORDER BY cr.final_confidence ASC
LIMIT 20;
```

### Output -- Demo-Cases als CSV exportieren

Sobald die drei Buckets gewaehlt sind, exportieren wir Top-3 aus jedem Bucket
als CSV fuer die Talk-Demo (statt der fiktiven Cases aus dem v5-Lovable-Prompt):

```bash
docker exec vigilex-postgres psql -U vigilex -d vigilex -c "\COPY (
  <SELECT ... LIMIT 3>
) TO STDOUT WITH CSV HEADER" > demo_cases.csv
```

---

## Phase 2: LLM-as-judge Setup

### Tabellen-Schema fuer Eval-Ergebnisse

```sql
CREATE TABLE IF NOT EXISTS processed.judge_evaluations (
    id                    BIGSERIAL PRIMARY KEY,
    coding_result_id      BIGINT NOT NULL REFERENCES processed.coding_results(id),
    judge_model           TEXT NOT NULL,        -- z.B. 'qwen2.5:7b' oder 'self-llama3.2:3b'
    judge_prompt_version  TEXT NOT NULL,        -- z.B. 'judge_v1'
    verdict               TEXT NOT NULL,        -- 'correct' | 'defensible' | 'wrong' | 'parse_error'
    reason                TEXT,                 -- Klartext-Begruendung des Judges
    judge_confidence      NUMERIC,              -- ordinal rating des Judges
    raw_response          TEXT,                 -- volles JSON-Output des Judges
    judged_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (coding_result_id, judge_model, judge_prompt_version)
);

CREATE INDEX idx_judge_eval_verdict ON processed.judge_evaluations (verdict);
CREATE INDEX idx_judge_eval_coding_result ON processed.judge_evaluations (coding_result_id);
```

### Judge-Modell-Wahl: drei Optionen

| Variante | Modell | Pro | Contra |
|---|---|---|---|
| A | Qwen2.5:7b lokal | Privacy OK, andere Modell-Familie -> wenig korrelierter Bias | Braucht zweite Ollama-Instanz oder Slot-Sharing mit Hauptmodell |
| B | Mistral 7B lokal | Wie A, andere Architektur | Wie A; und CX33 RAM ist eng |
| C | llama3.2:3b mit anderem Prompt | Kein zusaetzliches Modell noetig | Self-bias, schwacher Judge |

**Empfehlung fuer Capstone-Scope:** Variante C zuerst (kein Setup-Overhead),
spaeter Variante A wenn Hardware-Budget oder Cloud-Sub-Stack vorhanden ist.

### Judge-Prompt v1 (Variante C, self-judge mit anderem Prompt)

```
SYSTEM:
You are an independent reviewer evaluating MedDRA coding decisions.
You must NOT defer to the original coding system. Judge solely on whether
the chosen PT is clinically defensible given the narrative.

USER:
Narrative:
{narrative}

System's chosen PT: {pt_name} (pt_code {pt_code})
System's stated reason: {rationale}

Other top-5 candidates the system considered:
{other_candidates_list}

Task:
- Output ONLY valid JSON, no extra text
- Schema:
  {
    "verdict":          "correct" | "defensible" | "wrong",
    "reason":           "<one sentence>",
    "judge_confidence": <float 0.0-1.0>
  }

Definitions:
- "correct"     -> the chosen PT is clearly the best match
- "defensible" -> reasonable choice but other candidates also plausible
- "wrong"       -> a better candidate exists in the top-5 list
```

### Eval-Loop (Python-Skizze)

```python
# scripts/run_llm_judge.py (Capstone Phase 2 milestone)

import psycopg2
import requests
import json

JUDGE_MODEL = "llama3.2:3b"      # Variante C; spaeter qwen2.5:7b fuer Variante A
PROMPT_VERSION = "judge_v1"

def fetch_to_judge(conn, limit=50):
    """Hole Records die noch nicht von diesem Judge bewertet wurden."""
    sql = """
      SELECT cr.id, cr.pt_code, cr.pt_name, cr.rationale,
             mdr.mdr_text, cr.crossencoder_score, cr.final_confidence
      FROM processed.coding_results cr
      JOIN raw.maude_reports mdr USING (mdr_report_key)
      LEFT JOIN processed.judge_evaluations je
        ON je.coding_result_id = cr.id
       AND je.judge_model = %s
       AND je.judge_prompt_version = %s
      WHERE cr.llm_status = 'success'
        AND je.id IS NULL
      LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (JUDGE_MODEL, PROMPT_VERSION, limit))
        return cur.fetchall()

def judge_one(narrative, suggestion, rationale, alternatives):
    prompt = build_judge_prompt(narrative, suggestion, rationale, alternatives)
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": JUDGE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
        },
        timeout=60,
    )
    return json.loads(response.json()["message"]["content"])

# main loop: fetch -> judge -> insert -> repeat
```

---

## Phase 3: Aggregat-Metriken fuer die Final-Praesentation

Sobald `processed.judge_evaluations` gefuellt ist, kann auf die Slide 8
("What we can measure today") des Final-Presentation-Decks eine echte
Zahl fuer "LLM-as-judge agreement" eingetragen werden.

### Top-Level-Metrik

```sql
SELECT
  judge_model,
  COUNT(*)                                         AS total_judged,
  COUNT(*) FILTER (WHERE verdict = 'correct')      AS correct,
  COUNT(*) FILTER (WHERE verdict = 'defensible')   AS defensible,
  COUNT(*) FILTER (WHERE verdict = 'wrong')        AS wrong,
  ROUND(100.0 *
    (COUNT(*) FILTER (WHERE verdict IN ('correct', 'defensible')))
    / NULLIF(COUNT(*), 0), 1) AS pct_agreement
FROM processed.judge_evaluations
GROUP BY 1;
```

### Disagreement-Analyse (interessante Faelle fuer Manual-Review)

```sql
-- Wo der Judge dem System widerspricht UND System hohe Confidence hatte
SELECT
  cr.mdr_report_key,
  cr.pt_name        AS system_chose,
  cr.final_confidence,
  je.verdict,
  je.reason         AS judge_reason
FROM processed.coding_results cr
JOIN processed.judge_evaluations je ON je.coding_result_id = cr.id
WHERE je.verdict = 'wrong'
  AND cr.final_confidence > 0.7
ORDER BY cr.final_confidence DESC
LIMIT 50;
```

Diese Liste ist Gold fuer:
- Prompt-Tuning des Hauptsystems
- Identifikation systematischer Failure-Modi
- spaeter: Seed-Set fuer Expert-Labels

### Confidence-Calibration-Check

```sql
-- Bekommen high-confidence Predictions mehr 'correct' als low-confidence?
SELECT
  CASE
    WHEN cr.final_confidence >= 0.8 THEN '0.8-1.0'
    WHEN cr.final_confidence >= 0.6 THEN '0.6-0.8'
    WHEN cr.final_confidence >= 0.4 THEN '0.4-0.6'
    WHEN cr.final_confidence >= 0.2 THEN '0.2-0.4'
    ELSE '0.0-0.2'
  END AS confidence_bucket,
  COUNT(*) AS n,
  ROUND(100.0 * COUNT(*) FILTER (WHERE je.verdict = 'correct') / NULLIF(COUNT(*), 0), 1)
    AS pct_correct_per_bucket
FROM processed.coding_results cr
JOIN processed.judge_evaluations je ON je.coding_result_id = cr.id
GROUP BY 1
ORDER BY 1 DESC;
```

Wenn `pct_correct_per_bucket` monoton mit der Confidence steigt, ist das
ranking_index tatsaechlich ein nuetzlicher Triage-Signal. Wenn nicht, muss
die Mischformel (0.3 * sigmoid(CE) + 0.7 * LLM_ordinal) neu kalibriert werden.

---

## Phase 4: Vorbereitung fuer Expert-Labels (Beyond Capstone)

Wenn nach Capstone-Ende Expert-Reviewer eingebunden werden koennen, brauchen
wir eine Tabelle dafuer:

```sql
CREATE TABLE IF NOT EXISTS processed.expert_labels (
    id                  BIGSERIAL PRIMARY KEY,
    coding_result_id    BIGINT NOT NULL REFERENCES processed.coding_results(id),
    expert_id           TEXT NOT NULL,
    correct_pt_code     INTEGER,              -- der eigentlich richtige Code laut Expert
    expert_verdict      TEXT NOT NULL,        -- 'top_choice' | 'top_5' | 'not_in_top_5'
    expert_notes        TEXT,
    labeled_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Damit dann saubere Recall@5-Berechnung:

```sql
SELECT
  ROUND(100.0 *
    COUNT(*) FILTER (WHERE el.expert_verdict IN ('top_choice', 'top_5'))
    / NULLIF(COUNT(*), 0), 1) AS recall_at_5_pct,
  ROUND(100.0 *
    COUNT(*) FILTER (WHERE el.expert_verdict = 'top_choice')
    / NULLIF(COUNT(*), 0), 1) AS top1_accuracy_pct
FROM processed.expert_labels el;
```

---

## Parameter-Optimization (nach Eval-Infra)

Mit `judge_evaluations` als Loss-Funktion koennen wir die tunbaren Parameter
durchprobieren:

| Stage | Parameter | aktueller Wert | Tuning-Range |
|---|---|---|---|
| Stage 1 RRF | `w_bm25`     | 0.4 | 0.2 - 0.6 |
| Stage 1 RRF | `w_vec`      | 0.6 | 0.4 - 0.8 |
| Stage 1 RRF | `k`          | 60  | 30 - 100 |
| Stage 1 -> 2 | top_k aus RRF | 20 | 10 - 40 |
| Stage 2 -> 3 | top_k aus reranker | 5 | 3 - 10 |
| Final | ranking_index mix | (0.3, 0.7) | (0.2, 0.8) - (0.5, 0.5) |

Grid-Search auf einer Stichprobe (~200 Cases), Loss = LLM-as-judge agreement rate.
Caveat: LLM-as-judge ist nicht unabhaengig vom Hauptmodell, also Optimization
hier ist eine Approximation, kein echtes optimum. Vor Production-Deployment
muss mit Expert-Labels nachvalidiert werden.

---

## Talk-Sprachregelung (gilt fuer Talks zu diesem Plan)

Im Final-Talk (3. Juni) auf der Quality-Slide wird stehen:

> *"LLM-as-judge agreement: X% on Y QFG records, qwen2.5:7b as judge.
>  Independent expert labels remain future work."*

NIE als "X% accuracy" verkaufen. Es ist ein Agreement-Mass zwischen zwei
LLMs, kein Wahrheits-Mass. Die Talk-Defense lautet:

> *"This is a self-consistency measure, not a ground-truth measure.
>  It tells us where the system is consistent with an independent
>  language model -- which is useful for catching obvious failures
>  but does not replace expert validation."*

---

## Verweise

- DB-Schema-Details: `~/memory/reference_vigilex_schema.md` (Memory-System)
  und `vigilex/CLAUDE.md` Abschnitt "Erledigte Schritte (Block D)"
- Sprachregelung "ordinal rating" / "ranking index": `vigilex/CLAUDE.md`
  Abschnitt "Ranking Index / LLM Ordinal -- Sprachregelung"
- Mid-Term Slides die diesen Plan referenzieren:
  `presentations/FRIDAY-TALKS/TALK-2/lovable_prompt_talk2_v5_final.md`
  Slide 09 Spalte "BY 3 JUN" + Spalte "BEYOND CAPSTONE"

---

## To-Do bis 3. Juni

**Eval-Pipeline (Stand 2026-05-26):**
- [x] Golden Set erstellt: `data/eval/golden_set_v1.jsonl` (24 Cases, 3 Devices)
- [x] `eval_golden_set.py` mit MLflow-Logging, soft_recall, category breakdown
- [x] acceptable_pt_codes fuer 8 Miss-Cases (patch_golden_set_acceptable.py)
- [x] Miss-Analyse (analyze_misses.py): Bottleneck-Typen dokumentiert
- [x] LLT-Expansion Tabelle + Embedding gestartet (embed_meddra_llt_expanded.py)
- [ ] LLT-Expansion Index + hybrid_search.py Update (nach Embed-Fertig)
- [ ] LLT-Eval-Vergleich: R@100 + R@5 mit LLT-expanded vs. pt_only

**LLM-as-judge (Phase 2, noch offen):**
- [ ] SQL-Queries aus Phase 1 laufen lassen, 3x3 Demo-Cases als CSV exportieren
- [ ] Migration: `processed.judge_evaluations` Tabelle anlegen
- [ ] Judge-Prompt v1 als Python-Skizze in `scripts/run_llm_judge.py` bauen
- [ ] Eval-Loop fuer mind. 100 Records laufen lassen (Variante C, llama3.2:3b self-judge)
- [ ] Aggregat-Metrik in Final-Talk-Deck einfuegen
- [ ] Falls Zeit: Qwen2.5:7b zusaetzlich als unabhaengiger Judge (Variante A)
