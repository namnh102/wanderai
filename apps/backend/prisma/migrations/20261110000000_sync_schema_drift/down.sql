-- Reverse 20261110000000_sync_schema_drift
DROP INDEX IF EXISTS "documents_embedding_hnsw_idx";
DROP INDEX IF EXISTS "documents_destination_id_idx";
DROP INDEX IF EXISTS "documents_source_name_idx";
DROP INDEX IF EXISTS "documents_content_hash_embedding_model_key";

ALTER TABLE "documents"
  DROP COLUMN IF EXISTS "embedding",
  DROP COLUMN IF EXISTS "updated_at",
  DROP COLUMN IF EXISTS "retrieved_at",
  DROP COLUMN IF EXISTS "embedding_model",
  DROP COLUMN IF EXISTS "content_hash",
  DROP COLUMN IF EXISTS "title",
  DROP COLUMN IF EXISTS "section_heading",
  DROP COLUMN IF EXISTS "topic",
  DROP COLUMN IF EXISTS "language",
  DROP COLUMN IF EXISTS "place_id",
  DROP COLUMN IF EXISTS "destination_id",
  DROP COLUMN IF EXISTS "attribution",
  DROP COLUMN IF EXISTS "license",
  DROP COLUMN IF EXISTS "source_url",
  DROP COLUMN IF EXISTS "source_name",
  DROP COLUMN IF EXISTS "document_id";

DROP TABLE IF EXISTS "dataset_registry";

ALTER TABLE "trips"
  DROP COLUMN IF EXISTS "interests",
  DROP COLUMN IF EXISTS "travel_style",
  DROP COLUMN IF EXISTS "currency";
