"""
embed_meddra_terms_v2.py -- Generate all-mpnet-base-v2 embeddings for MedDRA PT names.

Writes 768-dim vectors into processed.meddra_terms.embedding_mpnet.
Prerequisite: migration 004_embedding_mpnet.sql must have been run.

Pool strategy: pt_only -- embed pt_name only (no LLT context).
Rationale: bench 2026-05-26 showed pt_only > pt_limited_llt across all models.

Usage on Hetzner:
    cd ~/vigilex
    export DATABASE_URL="postgresql://vigilex:...@127.0.0.1:5432/vigilex"
    export PYTHONPATH=src
    python3 scripts/embed_meddra_terms_v2.py
    python3 scripts/embed_meddra_terms_v2.py --batch-size 32   # lower if OOM
    python3 scripts/embed_meddra_terms_v2.py --dry-run
    python3 scripts/embed_meddra_terms_v2.py --force           # re-embed all rows
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2-binary not installed.")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit("sentence-transformers not installed. Run: pip3 install sentence-transformers")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME    = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM = 768
DEFAULT_BATCH = 64


def get_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB",   "vigilex")
    user = os.getenv("POSTGRES_USER", "vigilex")
    pw   = os.getenv("POSTGRES_PASSWORD", "")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def load_pending(conn, force: bool) -> list[tuple[int, str]]:
    """Return (pt_code, pt_name) rows to embed.

    Normal mode: only rows where embedding_mpnet IS NULL (idempotent).
    --force mode: all rows, including already-embedded ones.
    """
    sql = "SELECT pt_code, pt_name FROM processed.meddra_terms"
    if not force:
        sql += " WHERE embedding_mpnet IS NULL"
    sql += " ORDER BY pt_code"
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def write_embeddings(conn, codes: list[int], embeddings) -> None:
    sql = """
        UPDATE processed.meddra_terms
        SET embedding_mpnet = %s::vector
        WHERE pt_code = %s
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            sql,
            [(str(emb.tolist()), code) for code, emb in zip(codes, embeddings)],
            page_size=200,
        )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed MedDRA PT names with all-mpnet-base-v2 -> embedding_mpnet column"
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--dry-run", action="store_true",
                        help="Encode first batch, do not write to DB")
    parser.add_argument("--force", action="store_true",
                        help="Re-embed all rows, including already-populated ones")
    args = parser.parse_args()

    log.info("Model: %s", MODEL_NAME)
    log.info("Pool: pt_name only")
    log.info("Started: %s", datetime.now().isoformat())
    if args.force:
        log.info("--force: re-embedding all rows")

    db_url = get_db_url()
    if not db_url:
        sys.exit("DATABASE_URL not set.")

    log.info("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        sys.exit(f"DB connection failed: {e}")

    rows = load_pending(conn, force=args.force)
    if not rows:
        log.info("All embedding_mpnet values already populated. Nothing to do. Use --force to re-embed.")
        conn.close()
        return

    log.info("Rows to embed: %d", len(rows))

    log.info("Loading model: %s", MODEL_NAME)
    t0    = time.time()
    model = SentenceTransformer(MODEL_NAME)
    log.info("Model ready in %.1fs", time.time() - t0)

    total      = len(rows)
    batch_size = args.batch_size
    t_start    = time.time()

    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        codes = [r[0] for r in batch]
        names = [r[1] for r in batch]

        # L2 normalization: <=> (cosine distance) works without it, but normalizing
        # makes cosine distance more robust and consistent -- good practice,
        # not a hard requirement from pgvector.
        embeddings = model.encode(
            names,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        if not args.dry_run:
            write_embeddings(conn, codes, embeddings)

        done    = i + len(batch)
        elapsed = time.time() - t_start
        eta     = (elapsed / done) * (total - done) if done > 0 else 0
        print(
            f"  [{done:>6,}/{total:,}]  {done/total*100:5.1f}%"
            f"  elapsed: {elapsed:5.0f}s  ETA: {eta:5.0f}s",
            end="\r",
        )

        if args.dry_run and i == 0:
            print(f"\n[dry-run] First batch OK. shape=({len(embeddings)}, {embeddings.shape[1]})")
            print(f"[dry-run] norm of first vector: {float((embeddings[0]**2).sum()**0.5):.6f}")
            print("[dry-run] No DB writes.")
            conn.close()
            return

    elapsed = time.time() - t_start
    print()
    log.info("Done. %d embeddings written in %.0fs (%.1f min)", total, elapsed, elapsed / 60)
    conn.close()


if __name__ == "__main__":
    main()
