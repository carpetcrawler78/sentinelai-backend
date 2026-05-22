# vigilex / SentinelAI
**MedDRA coding assistance for medical-device adverse-event reports**

A three-stage local pipeline that turns free-text MAUDE narratives into
ranked MedDRA Preferred Term suggestions. Built as Capstone II of the
neue fische AI Engineering Bootcamp 2025/2026.

Internal repo name: `vigilex`. Public name in presentations and portfolio:
`SentinelAI`.

---

## What it does

Medical-device manufacturers must code every adverse-event report against
the MedDRA terminology (~27k Preferred Terms) for regulatory submission.
Today this is manual: one safety officer per company, ~10 min per case,
~70% inter-coder agreement.

SentinelAI assists this workflow:

- **Narrows the choice** -- from 27,361 MedDRA PTs to a ranked top-5
  with a written rationale per candidate
- **Same method every time** -- removes day-to-day variation between coders
- **Reviewer stays in charge** -- the system suggests, the human decides;
  every step is persisted for regulatory records

The architecture is built around three EU regulations:
GDPR (no patient data outside EU), EU AI Act (high-risk = human-in-the-loop),
EU MDR (post-market surveillance + reproducible records).

---

## Three-stage pipeline

```
27k MedDRA terms                MAUDE narrative (free text)
        |                                |
        |                                v
        |               Stage 1 -- RETRIEVE  (~0.5 sec)
        |               PubMedBERT bi-encoder via pgvector
        |               +  pg_trgm trigram on pt_name + 88k LLT synonyms
        |               -> RRF fusion (w_lex=0.4, w_vec=0.6, k=60)
        |                                v
        |                            Top-20
        |                                v
        |               Stage 2 -- RERANK  (~20 ms)
        |               MiniLM cross-encoder, joint attention on (narrative, pt_name)
        |                                v
        |                             Top-5
        |                                v
        |               Stage 3 -- SUGGEST  (~5-50 sec)
        |               Llama 3.2:3b via Ollama, local on Hetzner CX33
        |               -> JSON: pt_code, ordinal_rating, rationale
        |                                v
        |                ranking_index = 0.3 * sigmoid(CE) + 0.7 * LLM_ordinal
        |                                v
        |                  Reviewer UI -- accept / correct / reject
        |                                v
        +--------> processed.coding_results (audit-grade row per case)
```

### Why hybrid retrieval?
BM25/trigram catches exact MedDRA-vocabulary matches; semantic search via
PubMedBERT catches paraphrases (`low blood sugar` ~ `Hypoglycaemia`).
RRF fuses the two ranks without depending on incompatible score scales.

### Why a cross-encoder in Stage 2?
The bi-encoder from Stage 1 compares pre-computed vectors; the cross-encoder
reads (narrative, candidate) jointly and catches negation, primary-vs-secondary,
and relation logic. Too slow for 27k candidates, fast enough for 20.

### Why a local LLM?
GDPR Art. 44 + the EU AI Act make external LLM APIs incompatible with
patient-data workflows. Llama 3.2:3b via Ollama on Hetzner CX33 keeps the
narrative inside EU infrastructure with a pinned model version.

---

## Vocabulary note

The pipeline emits `ranking_index` (combined Stage 2 + Stage 3 score) and
`LLM_ordinal_rating` (raw Stage 3 output). These are **heuristic ordinal
values**, not calibrated probabilities. The reviewer UI uses them as a triage
signal: higher means earlier in the review queue, NOT "X% correct".

The DB columns are still named `llm_confidence` and `final_confidence` for
historical reasons -- that is tech debt and the names will be aligned in a
future migration.

---

## Repository layout

```
vigilex/
|-- src/vigilex/
|   |-- coding/           # Stage 1-3 implementations
|   |   |-- hybrid_search.py    # PubMedBERT + pg_trgm + RRF
|   |   |-- reranker.py         # MiniLM CrossEncoder
|   |   |-- llm_coder.py        # Llama via Ollama
|   |   `-- embed_meddra_terms.py
|   |-- workers/          # CodingWorker (SQL queue + polling)
|   |-- data/             # MAUDE client + flatten_maude_record()
|   |-- db/               # psycopg2 connection helpers
|   |-- api/              # FastAPI REST endpoints
|   `-- signals/          # PRR/ROR disproportionality (skeleton)
|-- docker/               # Compose stack: Postgres, Ollama, Worker, API
|-- grafana/              # Dashboards + datasources (provisioned)
|-- notebooks/            # 01-09: EDA, hybrid search, reranker, LLM, debugging
|-- tests/                # pytest suite (PRR/ROR + smoke tests)
|-- API.md                # REST API documentation
|-- CLAUDE.md             # AI-assistant project briefing (READ THIS FIRST)
|-- EVAL_PLAN.md          # Post-Midterm evaluation plan + LLM-as-judge setup
|-- DEVLOG.md             # chronological development diary
`-- README.md             # this file
```

---

## Data sources

| Source | Role |
|---|---|
| [openFDA MAUDE](https://open.fda.gov/apis/device/event/) | adverse-event narratives + device metadata |
| [MedDRA v29.0](https://www.meddra.org/) | ~27k Preferred Terms + 88k Lowest Level Term synonyms |
| EU MDR 2017/745, EU AI Act, GDPR | architectural constraints (not RAG content) |

MedDRA is licensed -- data files live outside version control (`.gitignore`).

---

## Setup (local development)

```bash
# Clone and install
git clone https://github.com/carpetcrawler78/vigilex.git
cd vigilex
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Configure (Hetzner DB connection string + Ollama URL)
cp .env.example .env
# Edit .env with your DATABASE_URL, OLLAMA_BASE_URL, API_KEY

# Optional: openFDA API key (raises rate limit from 1k to 120k req/day)
# Free at https://open.fda.gov/apis/authentication/
```

Production stack runs entirely in Docker on Hetzner CX33 (Nuremberg). See
`docker/docker-compose.yml` for the full service topology (Postgres + pgvector,
Ollama, MAUDE ingest worker, coding worker, FastAPI, Grafana).

---

## Status (2026-05-21)

- **Ingestion** -- 3 device cohorts ingested (LZG insulin pumps,
  OYC pacemakers, QFG CGM sensors)
- **Coding** -- 11,161 reports coded across the three device types
  (LZG 9,993, OYC 658, QFG 510)
- **Schema** -- coding_results extended 2026-05-19 with operational logging
  columns (`llm_status`, `coding_path`, `fallback_reason`, `rationale`, etc.)
- **REST API** -- `src/vigilex/api/main.py`, X-API-Key auth, deployed via Docker
- **Grafana** -- dashboard `sentinelai-coding-v1` provisioned
- **Mid-Term Talk** -- 2026-05-22, materials in
  `../presentations/FRIDAY-TALKS/TALK-2/`

See `CLAUDE.md` for the full status block and `EVAL_PLAN.md` for the
post-Midterm evaluation roadmap.

---

## Roadmap

**Capstone, second half (22 May - 3 June)**
- Reviewer UI end-to-end (`reviewer_action` columns persist accept/correct/reject)
- LLM-as-judge agreement measurement (see `EVAL_PLAN.md`)
- Grafana dashboard finalised + REST API deployed
- Friday Talk #3 = dry run for Final Presentation

**Beyond Capstone**
- Expert-labeled reference set -> strict recall@5 measurement
- Parameter optimization via LLM-as-judge loss function
- Full historical MAUDE import (2015-2024)
- Statistical signal detection on coded data (PRR/ROR)
- EUDAMED integration (mandate ~May 2026)
- LoRA finetuning of LLM on FDA adverse-event language

---

## Background

Built by Thomas Heger -- Dr. sc. ETH Biochemistry, former Clinical Data Manager
at DKFZ Heidelberg (REQUITE, RADprecise post-market surveillance studies).
Domain expertise in GCP documentation, MDR conformity, and EU regulatory
context informs both the architecture choices and the talk framing of this
project.

---

## License

MIT
