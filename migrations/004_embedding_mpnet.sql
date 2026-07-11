-- Migration 004: add mpnet embedding column to meddra_terms
-- Prerequisite: vector extension already active (pgvector)
-- Run after review:
--   psql -h 127.0.0.1 -U vigilex -d vigilex -f migrations/004_embedding_mpnet.sql

ALTER TABLE processed.meddra_terms
    ADD COLUMN IF NOT EXISTS embedding_mpnet vector(768);
