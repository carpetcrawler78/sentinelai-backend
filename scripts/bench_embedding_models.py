"""
bench_embedding_models.py -- Embedding model benchmark for MedDRA vector search.

Usage on Hetzner:
    cd ~/vigilex && export PYTHONPATH=src

    # Phase 1 PoC (one config):
    python3 scripts/bench_embedding_models.py

    # Phase 2 full matrix (3 models x 2 pools x 2 query fields = 12 configs):
    python3 scripts/bench_embedding_models.py --full 2>&1 | tee data/eval/bench_run.log
"""

import argparse
import csv
import json
import logging
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    import numpy as np
except ImportError:
    sys.exit("numpy not installed.")

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2-binary not installed.")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit("sentence-transformers not installed.")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODELS_POC = ["sentence-transformers/all-MiniLM-L6-v2"]
MODELS_FULL = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "BAAI/bge-small-en-v1.5",
    "sentence-transformers/all-mpnet-base-v2",
]
POOL_TYPES_POC   = ["pt_only"]
POOL_TYPES_FULL  = ["pt_only", "pt_limited_llt"]
QUERY_FIELDS_POC  = ["first_sentence"]
QUERY_FIELDS_FULL = ["first_sentence", "full_text_truncated"]

EVAL_PATH   = ROOT / "data/eval/golden_set_v1.jsonl"
CACHE_DIR   = ROOT / "data/eval/cache"
SUMMARY_CSV = ROOT / "data/eval/bench_results_summary.csv"
DETAIL_CSV  = ROOT / "data/eval/bench_results_detailed.csv"

SUMMARY_COLS = [
    "model", "pool_type", "query_field", "n", "max_seq_length",
    "exact_recall_at_1", "exact_recall_at_5", "exact_recall_at_20",
    "exact_recall_at_50", "exact_recall_at_100",
    "median_rank_found", "mean_rank_found_only", "not_found_count",
]
DETAIL_COLS = [
    "model", "pool_type", "query_field", "case_id", "mdr_report_key",
    "expected_pt_code", "expected_pt_name", "primary_rank",
    "top1_code", "top1_name", "top5_names", "top20_names",
    "query_text_used", "query_length_chars",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def model_slug(model_name: str) -> str:
    return (
        model_name.replace("/", "__")
                  .replace("-", "_")
                  .replace(".", "_")
    )


def cache_path(model_name: str, dim: int, pool_type: str, kind: str) -> Path:
    # kind: "doc_embeddings.npy" | "pt_codes.npy" | "meta.csv"
    slug = model_slug(model_name)
    return CACHE_DIR / f"{slug}_dim{dim}_{pool_type}_{kind}"


def make_first_sentence(text: str) -> str:
    s = text.split(".")[0].strip()
    return s[:1000] if s else text[:1000]


def build_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER", "vigilex")
    pw   = os.environ.get("POSTGRES_PASSWORD", "")
    db   = os.environ.get("POSTGRES_DB", "vigilex")
    return f"postgresql://{user}:{pw}@localhost:5432/{db}"


# ---------------------------------------------------------------------------
# Pool loading
# ---------------------------------------------------------------------------

def load_pool_pt_only(conn) -> list:
    sql = """
        SELECT pt_code, pt_name, pt_name AS search_text
        FROM processed.meddra_terms
        ORDER BY pt_code
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [{"pt_code": r[0], "pt_name": r[1], "search_text": r[2]} for r in rows]


def load_pool_pt_limited_llt(conn) -> list:
    # Up to 10 LLT synonyms per PT, shortest first, LLT != pt_name.
    # CASE avoids trailing pipe when no synonyms exist (validated in Phase 1 Step 2).
    sql = """
        WITH llt_limited AS (
            SELECT
                pt_code,
                llt_name,
                ROW_NUMBER() OVER (
                    PARTITION BY pt_code
                    ORDER BY LENGTH(llt_name), llt_name
                ) AS rn
            FROM processed.meddra_llt
            WHERE llt_name IS NOT NULL
        )
        SELECT
            t.pt_code,
            t.pt_name,
            CASE
                WHEN string_agg(l.llt_name, ' | ') IS NOT NULL
                THEN t.pt_name || ' | ' || string_agg(l.llt_name, ' | ')
                ELSE t.pt_name
            END AS search_text
        FROM processed.meddra_terms t
        LEFT JOIN llt_limited l
            ON t.pt_code = l.pt_code
            AND l.rn <= 10
            AND l.llt_name <> t.pt_name
        GROUP BY t.pt_code, t.pt_name
        ORDER BY t.pt_code
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [{"pt_code": r[0], "pt_name": r[1], "search_text": r[2]} for r in rows]


def load_pool(conn, pool_type: str) -> list:
    if pool_type == "pt_only":
        return load_pool_pt_only(conn)
    if pool_type == "pt_limited_llt":
        return load_pool_pt_limited_llt(conn)
    raise ValueError(f"Unknown pool_type: {pool_type}")


# ---------------------------------------------------------------------------
# Sanity check -- runs BEFORE model load
# ---------------------------------------------------------------------------

def sanity_check(golden: list, pool: list) -> None:
    expected_codes = {int(c["expected_pt_code"]) for c in golden}
    pool_codes     = {int(r["pt_code"]) for r in pool}
    missing        = expected_codes - pool_codes
    assert not missing, f"Expected PT codes missing from pool: {missing}"
    print(f"  Sanity check OK -- all {len(expected_codes)} expected PT codes "
          f"present in pool ({len(pool_codes)} total PTs)")


# ---------------------------------------------------------------------------
# Doc embedding cache
# ---------------------------------------------------------------------------

def encode_or_load_docs(
    model: SentenceTransformer,
    model_name: str,
    pool: list,
    pool_type: str,
) -> tuple:
    """Return (doc_emb ndarray, pt_codes ndarray, pt_names list)."""
    dim        = model.get_sentence_embedding_dimension()
    emb_path   = cache_path(model_name, dim, pool_type, "doc_embeddings.npy")
    codes_path = cache_path(model_name, dim, pool_type, "pt_codes.npy")
    meta_path  = cache_path(model_name, dim, pool_type, "meta.csv")

    if emb_path.exists() and codes_path.exists() and meta_path.exists():
        print(f"  [CACHE HIT]  {emb_path.name}")
        doc_emb  = np.load(emb_path)
        pt_codes = np.load(codes_path)
        with open(meta_path, encoding="utf-8") as f:
            pt_names = [row["pt_name"] for row in csv.DictReader(f)]
        print(f"  Loaded shape={doc_emb.shape}, {len(pt_names)} PT names")
        return doc_emb, pt_codes, pt_names

    print(f"  [CACHE MISS] Encoding {len(pool)} documents with {model_name} ...")
    texts    = [r["search_text"] for r in pool]
    pt_codes = np.array([r["pt_code"] for r in pool], dtype=np.int64)
    pt_names = [r["pt_name"] for r in pool]

    t0 = time.time()
    doc_emb = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=256,
        show_progress_bar=True,
    )
    print(f"  Encoded in {time.time()-t0:.1f}s, shape={doc_emb.shape}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(emb_path, doc_emb)
    np.save(codes_path, pt_codes)
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pt_code", "pt_name", "search_text"])
        writer.writeheader()
        writer.writerows(pool)
    print(f"  Cache saved -> {emb_path.name}")

    return doc_emb, pt_codes, pt_names


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_config(
    model_name: str,
    pool_type: str,
    query_field: str,
    golden: list,
    doc_emb,
    pt_codes,
    pt_names: list,
    model: SentenceTransformer,
) -> tuple:
    """Return (summary_row dict, detail_rows list)."""
    query_texts = []
    for case in golden:
        if query_field == "first_sentence":
            query_texts.append(make_first_sentence(case["mdr_text"]))
        else:
            query_texts.append(case["mdr_text"].strip()[:2048])

    t0 = time.time()
    q_emb = model.encode(
        query_texts,
        normalize_embeddings=True,
        batch_size=64,
        show_progress_bar=False,
    )
    print(f"  Query encoding: {time.time()-t0:.2f}s for {len(query_texts)} queries")

    # Cosine via dot product (both sides L2-normalized)
    scores_matrix = doc_emb @ q_emb.T   # shape (N_pool, N_cases)

    pt_code_list = pt_codes.tolist()
    detail_rows  = []
    ranks        = []

    for i, case in enumerate(golden):
        expected_code = int(case["expected_pt_code"])
        order         = np.argsort(scores_matrix[:, i])[::-1]

        rank = None
        for pos, idx in enumerate(order, 1):
            if pt_code_list[idx] == expected_code:
                rank = pos
                break

        ranks.append(rank)

        top_idxs    = order[:20].tolist()
        top5_names  = " | ".join(pt_names[j] for j in top_idxs[:5])
        top20_names = " | ".join(pt_names[j] for j in top_idxs[:20])

        detail_rows.append({
            "model":              model_name,
            "pool_type":          pool_type,
            "query_field":        query_field,
            "case_id":            i + 1,
            "mdr_report_key":     case["mdr_report_key"],
            "expected_pt_code":   expected_code,
            "expected_pt_name":   case["expected_pt_name"],
            "primary_rank":       rank if rank is not None else "",
            "top1_code":          pt_code_list[top_idxs[0]],
            "top1_name":          pt_names[top_idxs[0]],
            "top5_names":         top5_names,
            "top20_names":        top20_names,
            "query_text_used":    query_texts[i],
            "query_length_chars": len(query_texts[i]),
        })

    # "not_found" = rank > 100, consistent with baseline_vector_only.py
    n         = len(golden)
    found_100 = [r for r in ranks if r is not None and r <= 100]
    not_found = sum(1 for r in ranks if r is None or r > 100)

    def recall_at_k(k: int) -> float:
        return round(sum(1 for r in ranks if r is not None and r <= k) / n, 4)

    summary = {
        "model":                model_name,
        "pool_type":            pool_type,
        "query_field":          query_field,
        "n":                    n,
        "max_seq_length":       model.max_seq_length,
        "exact_recall_at_1":    recall_at_k(1),
        "exact_recall_at_5":    recall_at_k(5),
        "exact_recall_at_20":   recall_at_k(20),
        "exact_recall_at_50":   recall_at_k(50),
        "exact_recall_at_100":  recall_at_k(100),
        "median_rank_found":    round(statistics.median(found_100), 1) if found_100 else "",
        "mean_rank_found_only": round(statistics.mean(found_100), 1)   if found_100 else "",
        "not_found_count":      not_found,
    }
    return summary, detail_rows


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def config_in_summary(model_name: str, pool_type: str, query_field: str) -> bool:
    if not SUMMARY_CSV.exists():
        return False
    with open(SUMMARY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row["model"] == model_name
                    and row["pool_type"] == pool_type
                    and row["query_field"] == query_field):
                return True
    return False


def append_csv(path: Path, cols: list, rows: list) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--full", action="store_true",
                   help="Run full matrix (3 models x 2 pools x 2 query fields). "
                        "Default: single PoC config.")
    return p.parse_args()


def run_one_config(
    model_name: str,
    pool_type: str,
    query_field: str,
    golden: list,
    pools: dict,
    model: SentenceTransformer,
) -> None:
    tag = f"{model_name} / {pool_type} / {query_field}"

    if config_in_summary(model_name, pool_type, query_field):
        logging.info("[SKIP] Already done: %s", tag)
        print(f"  [SKIP] Already in summary: {tag}")
        return

    pool = pools[pool_type]

    logging.info("Starting: %s", tag)
    t0 = time.time()
    doc_emb, pt_codes, pt_names = encode_or_load_docs(model, model_name, pool, pool_type)
    doc_time = time.time() - t0

    summary, detail_rows = evaluate_config(
        model_name, pool_type, query_field,
        golden, doc_emb, pt_codes, pt_names, model,
    )
    append_csv(SUMMARY_CSV, SUMMARY_COLS, [summary])
    append_csv(DETAIL_CSV,  DETAIL_COLS,  detail_rows)

    msg = (f"DONE {tag} | R@1={summary['exact_recall_at_1']} "
           f"R@5={summary['exact_recall_at_5']} "
           f"R@100={summary['exact_recall_at_100']} "
           f"not_found={summary['not_found_count']} "
           f"doc_emb={doc_time:.0f}s")
    logging.info(msg)
    print(f"\n  {msg}")


def main() -> None:
    args = parse_args()

    # Logging to file (used in --full mode so tmux output is readable)
    log_dir = ROOT / "data/eval"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "bench_run.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.full:
        models      = MODELS_FULL
        pool_types  = POOL_TYPES_FULL
        query_fields = QUERY_FIELDS_FULL
        print(f"=== FULL BENCH: {len(models)} models x {len(pool_types)} pools "
              f"x {len(query_fields)} query fields "
              f"= {len(models)*len(pool_types)*len(query_fields)} configs ===\n")
    else:
        models      = MODELS_POC
        pool_types  = POOL_TYPES_POC
        query_fields = QUERY_FIELDS_POC
        print("=== PoC run (single config) ===\n")

    t_total = time.time()

    # Golden set
    if not EVAL_PATH.exists():
        sys.exit(f"Golden set not found: {EVAL_PATH}")
    with open(EVAL_PATH, encoding="utf-8") as f:
        golden = [json.loads(line) for line in f if line.strip()]
    print(f"Golden set: {len(golden)} cases")

    # Load all pools upfront (DB queries are fast, avoids repeated connections)
    print("Loading pools from DB...")
    conn = psycopg2.connect(build_db_url())
    pools = {}
    for pt in pool_types:
        t0 = time.time()
        pools[pt] = load_pool(conn, pt)
        print(f"  {pt}: {len(pools[pt])} PTs ({time.time()-t0:.1f}s)")
    conn.close()

    # Sanity check against first pool (pt_only always loaded)
    sanity_check(golden, pools["pt_only"])

    # Main loop: model -> pool -> query
    for model_name in models:
        print(f"\nLoading model: {model_name}")
        t0 = time.time()
        try:
            model = SentenceTransformer(model_name)
        except Exception as exc:
            logging.error("Failed to load model %s: %s", model_name, exc)
            print(f"  ERROR loading model: {exc} -- skipping all configs for this model")
            continue
        dim = model.get_sentence_embedding_dimension()
        print(f"  dim={dim}, max_seq_length={model.max_seq_length}, "
              f"loaded in {time.time()-t0:.1f}s")

        for pool_type in pool_types:
            for query_field in query_fields:
                try:
                    run_one_config(
                        model_name, pool_type, query_field,
                        golden, pools, model,
                    )
                except Exception as exc:
                    tag = f"{model_name}/{pool_type}/{query_field}"
                    logging.error("Config %s failed: %s", tag, exc)
                    print(f"  ERROR in {tag}: {exc} -- continuing")

    elapsed = time.time() - t_total
    print(f"\n=== Bench complete. Total elapsed: {elapsed:.0f}s "
          f"({elapsed/60:.1f} min) ===")
    print(f"Summary -> {SUMMARY_CSV}")
    print(f"Detail  -> {DETAIL_CSV}")
    logging.info("Bench complete. Elapsed %.0fs", elapsed)


if __name__ == "__main__":
    main()
