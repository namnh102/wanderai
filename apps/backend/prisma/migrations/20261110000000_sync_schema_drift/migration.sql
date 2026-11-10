-- Ensure required PostgreSQL extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- Note: trips columns ("currency", "interests", "travel_style") were already added in
-- historical migration 20261001083200_add_trip_context_fields and must not be re-owned here.

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

-- Step 1: Add missing documents columns as NULLABLE first so pre-existing rows never receive
-- fabricated provenance ('wikivoyage' / 'CC BY-SA 3.0') or colliding empty content_hash ('').
ALTER TABLE "documents"
  ADD COLUMN IF NOT EXISTS "document_id" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "source_name" VARCHAR(50),
  ADD COLUMN IF NOT EXISTS "source_url" VARCHAR(500),
  ADD COLUMN IF NOT EXISTS "license" VARCHAR(100),
  ADD COLUMN IF NOT EXISTS "attribution" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "destination_id" UUID,
  ADD COLUMN IF NOT EXISTS "place_id" UUID,
  ADD COLUMN IF NOT EXISTS "language" VARCHAR(10),
  ADD COLUMN IF NOT EXISTS "topic" VARCHAR(100),
  ADD COLUMN IF NOT EXISTS "section_heading" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "title" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "content_hash" VARCHAR(64),
  ADD COLUMN IF NOT EXISTS "embedding_model" VARCHAR(100),
  ADD COLUMN IF NOT EXISTS "retrieved_at" TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS "embedding" vector(384);

-- Step 2: Safely backfill pre-existing / unbackfilled / duplicate legacy rows in "documents"
-- without deleting any rows and without stamping fake provenance.
DO $$
DECLARE
  has_legacy_source_col BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = 'documents'
      AND column_name = 'source'
  ) INTO has_legacy_source_col;

  -- 2a. Normalize rows lacking provenance, embedding_model, or a valid 64-hex content_hash.
  IF has_legacy_source_col THEN
    EXECUTE $sql$
      UPDATE "documents"
      SET
        "metadata" = (
          CASE
            WHEN "metadata" IS NULL OR jsonb_typeof("metadata") = 'null' THEN '{}'::jsonb
            WHEN jsonb_typeof("metadata") = 'object' THEN "metadata"
            ELSE jsonb_build_object('legacy_raw_metadata', "metadata")
          END
          || jsonb_build_object(
            'legacy_migration_backfill', true,
            'user_citable', false,
            'scientific_corpus', false
          )
          || CASE
            WHEN "source" IS NOT NULL THEN jsonb_build_object('legacy_source_column', "source")
            ELSE '{}'::jsonb
          END
          || CASE
            WHEN "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$' THEN
              jsonb_build_object(
                'legacy_content_hash_backfilled', true,
                'legacy_invalid_content_hash', "content_hash"
              )
            ELSE '{}'::jsonb
          END
        ),
        "document_id" = COALESCE(NULLIF(btrim("document_id"), ''), 'legacy-doc-' || "id"::text),
        "source_name" = CASE
          WHEN "source_name" IS NULL OR btrim("source_name") = '' THEN 'unverified_legacy'
          ELSE "source_name"
        END,
        "source_url" = COALESCE("source_url", ''),
        "license" = CASE
          WHEN "license" IS NULL OR btrim("license") = '' THEN 'UNVERIFIED_LEGACY'
          ELSE "license"
        END,
        "attribution" = COALESCE("attribution", ''),
        "language" = CASE
          WHEN "language" IS NULL OR btrim("language") = '' THEN 'und'
          ELSE "language"
        END,
        "title" = COALESCE("title", ''),
        "embedding_model" = CASE
          WHEN "embedding_model" IS NULL OR btrim("embedding_model") = '' THEN
            CASE
              WHEN "embedding" IS NULL THEN 'unembedded_legacy'
              ELSE 'unknown_preexisting_model'
            END
          ELSE "embedding_model"
        END,
        "content_hash" = CASE
          WHEN "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$' THEN
            encode(
              sha256(
                convert_to(
                  'legacy-unbackfilled:' || "id"::text || ':' || COALESCE("content", ''),
                  'UTF8'
                )
              ),
              'hex'
            )
          ELSE lower("content_hash")
        END
      WHERE "source_name" IS NULL OR btrim("source_name") = ''
         OR "license" IS NULL OR btrim("license") = ''
         OR "embedding_model" IS NULL OR btrim("embedding_model") = ''
         OR "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$'
    $sql$;
  ELSE
    UPDATE "documents"
    SET
      "metadata" = (
        CASE
          WHEN "metadata" IS NULL OR jsonb_typeof("metadata") = 'null' THEN '{}'::jsonb
          WHEN jsonb_typeof("metadata") = 'object' THEN "metadata"
          ELSE jsonb_build_object('legacy_raw_metadata', "metadata")
        END
        || jsonb_build_object(
          'legacy_migration_backfill', true,
          'user_citable', false,
          'scientific_corpus', false
        )
        || CASE
          WHEN "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$' THEN
            jsonb_build_object(
              'legacy_content_hash_backfilled', true,
              'legacy_invalid_content_hash', "content_hash"
            )
          ELSE '{}'::jsonb
        END
      ),
      "document_id" = COALESCE(NULLIF(btrim("document_id"), ''), 'legacy-doc-' || "id"::text),
      "source_name" = CASE
        WHEN "source_name" IS NULL OR btrim("source_name") = '' THEN 'unverified_legacy'
        ELSE "source_name"
      END,
      "source_url" = COALESCE("source_url", ''),
      "license" = CASE
        WHEN "license" IS NULL OR btrim("license") = '' THEN 'UNVERIFIED_LEGACY'
        ELSE "license"
      END,
      "attribution" = COALESCE("attribution", ''),
      "language" = CASE
        WHEN "language" IS NULL OR btrim("language") = '' THEN 'und'
        ELSE "language"
      END,
      "title" = COALESCE("title", ''),
      "embedding_model" = CASE
        WHEN "embedding_model" IS NULL OR btrim("embedding_model") = '' THEN
          CASE
            WHEN "embedding" IS NULL THEN 'unembedded_legacy'
            ELSE 'unknown_preexisting_model'
          END
        ELSE "embedding_model"
      END,
      "content_hash" = CASE
        WHEN "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$' THEN
          encode(
            sha256(
              convert_to(
                'legacy-unbackfilled:' || "id"::text || ':' || COALESCE("content", ''),
                'UTF8'
              )
            ),
            'hex'
          )
        ELSE lower("content_hash")
      END
    WHERE "source_name" IS NULL OR btrim("source_name") = ''
       OR "license" IS NULL OR btrim("license") = ''
       OR "embedding_model" IS NULL OR btrim("embedding_model") = ''
       OR "content_hash" IS NULL OR "content_hash" !~ '^[0-9a-fA-F]{64}$';
  END IF;

  -- 2b. Fill any remaining nullable auxiliary fields on otherwise-valid rows without altering provenance.
  UPDATE "documents"
  SET
    "document_id" = COALESCE("document_id", ''),
    "source_url" = COALESCE("source_url", ''),
    "attribution" = COALESCE("attribution", ''),
    "language" = COALESCE(NULLIF(btrim("language"), ''), 'und'),
    "title" = COALESCE("title", ''),
    "retrieved_at" = COALESCE("retrieved_at", "created_at", CURRENT_TIMESTAMP),
    "updated_at" = COALESCE("updated_at", "created_at", CURRENT_TIMESTAMP)
  WHERE "document_id" IS NULL
     OR "source_url" IS NULL
     OR "attribution" IS NULL
     OR "language" IS NULL OR btrim("language") = ''
     OR "title" IS NULL
     OR "retrieved_at" IS NULL
     OR "updated_at" IS NULL;

  -- 2c. Disambiguate any pre-existing duplicate (content_hash, embedding_model) pairs without deleting rows.
  WITH ranked_duplicates AS (
    SELECT
      "id",
      "content_hash" AS original_hash,
      ROW_NUMBER() OVER (
        PARTITION BY "content_hash", "embedding_model"
        ORDER BY "created_at" ASC NULLS LAST, "id" ASC
      ) AS rn
    FROM "documents"
  )
  UPDATE "documents" d
  SET
    "content_hash" = encode(
      sha256(
        convert_to(
          'legacy-duplicate:' || d."id"::text || ':' || rd.original_hash,
          'UTF8'
        )
      ),
      'hex'
    ),
    "metadata" = (
      CASE
        WHEN d."metadata" IS NULL OR jsonb_typeof(d."metadata") = 'null' THEN '{}'::jsonb
        WHEN jsonb_typeof(d."metadata") = 'object' THEN d."metadata"
        ELSE jsonb_build_object('legacy_raw_metadata', d."metadata")
      END
      || jsonb_build_object(
        'legacy_migration_backfill', true,
        'user_citable', false,
        'scientific_corpus', false,
        'legacy_duplicate_of_content_hash', rd.original_hash
      )
    )
  FROM ranked_duplicates rd
  WHERE d."id" = rd."id"
    AND rd.rn > 1;
END $$;

-- Step 3: Enforce NOT NULL constraints and non-fabricated defaults aligned with schema.prisma.
-- Note: content_hash intentionally has NO default so future inserts cannot silently write ''.
ALTER TABLE "documents"
  ALTER COLUMN "document_id" SET DEFAULT '',
  ALTER COLUMN "document_id" SET NOT NULL,
  ALTER COLUMN "source_name" SET DEFAULT 'unverified_legacy',
  ALTER COLUMN "source_name" SET NOT NULL,
  ALTER COLUMN "source_url" SET DEFAULT '',
  ALTER COLUMN "source_url" SET NOT NULL,
  ALTER COLUMN "license" SET DEFAULT 'UNVERIFIED_LEGACY',
  ALTER COLUMN "license" SET NOT NULL,
  ALTER COLUMN "attribution" SET DEFAULT '',
  ALTER COLUMN "attribution" SET NOT NULL,
  ALTER COLUMN "language" SET DEFAULT 'und',
  ALTER COLUMN "language" SET NOT NULL,
  ALTER COLUMN "title" SET DEFAULT '',
  ALTER COLUMN "title" SET NOT NULL,
  ALTER COLUMN "content_hash" DROP DEFAULT,
  ALTER COLUMN "content_hash" SET NOT NULL,
  ALTER COLUMN "embedding_model" SET DEFAULT 'unembedded_legacy',
  ALTER COLUMN "embedding_model" SET NOT NULL,
  ALTER COLUMN "retrieved_at" SET DEFAULT CURRENT_TIMESTAMP,
  ALTER COLUMN "retrieved_at" SET NOT NULL,
  ALTER COLUMN "updated_at" SET DEFAULT CURRENT_TIMESTAMP,
  ALTER COLUMN "updated_at" SET NOT NULL;

-- Step 4: Create uniqueness, lookup, and pgvector HNSW indexes.
CREATE UNIQUE INDEX IF NOT EXISTS "documents_content_hash_embedding_model_key" ON "documents"("content_hash", "embedding_model");
CREATE INDEX IF NOT EXISTS "documents_source_name_idx" ON "documents"("source_name");
CREATE INDEX IF NOT EXISTS "documents_destination_id_idx" ON "documents"("destination_id");
CREATE INDEX IF NOT EXISTS "documents_embedding_hnsw_idx" ON "documents" USING hnsw ("embedding" vector_cosine_ops);
