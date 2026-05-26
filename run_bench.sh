#!/bin/bash
cd /home/cap/vigilex
set -a && source .env && set +a
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
export PYTHONPATH=src
python3 scripts/bench_embedding_models.py --full 2>&1 | tee data/eval/bench_run.log
