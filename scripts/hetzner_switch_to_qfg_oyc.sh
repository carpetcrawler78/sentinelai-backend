#!/bin/bash
# SentinelAI -- Switch coding queue von LZG-Rest auf QFG/OYC
# Ausfuehren auf Hetzner: bash ~/vigilex/scripts/hetzner_switch_to_qfg_oyc.sh

set -e
cd ~/vigilex

echo "=== [1/4] Worker stoppen ==="
docker compose stop worker-coding

echo "=== [2/4] Ingest QFG + OYC starten ==="
docker compose run --rm -d --name ingest-qfg worker-ingest python -m vigilex.workers.ingest --product-code QFG --year 2024 || \
    (export $(cat .env | grep -v '^#' | xargs) && PYTHONPATH=src python -m vigilex.workers.ingest --product-code QFG --year 2024 &)
docker compose run --rm -d --name ingest-oyc worker-ingest python -m vigilex.workers.ingest --product-code OYC --year 2024 || \
    (export $(cat .env | grep -v '^#' | xargs) && PYTHONPATH=src python -m vigilex.workers.ingest --product-code OYC --year 2024 &)

echo "=== [3/4] Verbleibende LZG-Records skippen ==="
docker exec -i vigilex-postgres psql -U vigilex -d vigilex <<'SQL'
INSERT INTO processed.coding_results
    (mdr_report_key, pt_code, pt_name, llt_code, llt_name, soc_name,
     vector_similarity, crossencoder_score, llm_confidence, final_confidence,
     model_version, coded_at)
SELECT r.mdr_report_key,
       'SKIP', 'SKIPPED_LZG', NULL, NULL, NULL,
       0.0, 0.0, 0.0, 0.0,
       'skipped_lzg_remainder', NOW()
FROM raw.maude_reports r
LEFT JOIN processed.coding_results cr ON r.mdr_report_key = cr.mdr_report_key
WHERE cr.id IS NULL;
SQL
echo "LZG-Rückstand geskippt: $(docker exec vigilex-postgres psql -U vigilex -d vigilex -tAc "SELECT COUNT(*) FROM processed.coding_results WHERE model_version='skipped_lzg_remainder'") Records"

echo "=== [4/4] Worker neu starten ==="
sleep 10
docker compose start worker-coding
echo "=== Fertig -- Worker laeuft jetzt durch QFG/OYC Queue ==="
echo "Check: docker logs -f vigilex-worker-coding"
