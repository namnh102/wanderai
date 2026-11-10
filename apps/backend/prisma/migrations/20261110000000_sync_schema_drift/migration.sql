-- Ensure required PostgreSQL extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- Sync trips table columns defined in schema.prisma
ALTER TABLE "trips"
  ADD COLUMN IF NOT EXISTS "currency" TEXT NOT NULL DEFAULT 'VND',
  ADD COLUMN IF NOT EXISTS "travel_style" "TravelStyle",
  ADD COLUMN IF NOT EXISTS "interests" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- Create dataset_registry table defined in schema.prisma
CREATE TABLE IF NOT EXISTS "dataset_registry" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "dataset_name" VARCHAR(100) NOT NULL,
    "dataset_source" VARCHAR(255) NOT NULL,
    "dataset_version" VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    "license" VARCHAR(100) NOT NULL,
    "access_status" VARCHAR(50) NOT NULL DEFAULT 'REQUEST_NOT_SENT',
    "retrieved_at" TIMESTAMPTZ,
    "checksum" VARCHAR(128),
    "restriction" VARCHAR(255) NOT NULL,
    "record_count" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "dataset_registry_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "dataset_registry_dataset_name_key" ON "dataset_registry"("dataset_name");

-- Sync documents table columns, pgvector embedding(384), and HNSW index
ALTER TABLE "documents"
  ADD COLUMN IF NOT EXISTS "document_id" VARCHAR(255) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS "source_name" VARCHAR(50) NOT NULL DEFAULT 'wikivoyage',
  ADD COLUMN IF NOT EXISTS "source_url" VARCHAR(500) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS "license" VARCHAR(100) NOT NULL DEFAULT 'CC BY-SA 3.0',
  ADD COLUMN IF NOT EXISTS "attribution" VARCHAR(255) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS "destination_id" UUID,
  ADD COLUMN IF NOT EXISTS "place_id" UUID,
  ADD COLUMN IF NOT EXISTS "language" VARCHAR(10) NOT NULL DEFAULT 'en',
  ADD COLUMN IF NOT EXISTS "topic" VARCHAR(100),
  ADD COLUMN IF NOT EXISTS "section_heading" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "title" VARCHAR(255) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS "content_hash" VARCHAR(64) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS "embedding_model" VARCHAR(100) NOT NULL DEFAULT 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
  ADD COLUMN IF NOT EXISTS "retrieved_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS "embedding" vector(384);

CREATE UNIQUE INDEX IF NOT EXISTS "documents_content_hash_embedding_model_key" ON "documents"("content_hash", "embedding_model");
CREATE INDEX IF NOT EXISTS "documents_source_name_idx" ON "documents"("source_name");
CREATE INDEX IF NOT EXISTS "documents_destination_id_idx" ON "documents"("destination_id");
CREATE INDEX IF NOT EXISTS "documents_embedding_hnsw_idx" ON "documents" USING hnsw ("embedding" vector_cosine_ops);
