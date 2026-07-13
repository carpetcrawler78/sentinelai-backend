#!/usr/bin/env bash
set -a
source /home/cap/vigilex/.env
set +a

export PYTHONPATH=/home/cap/vigilex/src
export DATABASE_URL="postgresql://${POSTGRES_USER:-vigilex}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-vigilex}"
export OLLAMA_BASE_URL=http://localhost:11434
export VIGILEX_STRICT=true
