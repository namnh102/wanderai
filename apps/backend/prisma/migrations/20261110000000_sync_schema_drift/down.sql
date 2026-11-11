-- Non-destructive & fail-closed rollback for 20261110000000_sync_schema_drift (PROD-CI-05 C02-F01).
--
-- Safety invariants:
-- 1. Never touches "trips" columns ("currency", "interests", "travel_style") owned by
--    20261001083200_add_trip_context_fields.
-- 2. Fails closed if "_migration_20261110_schema_ledger" is absent (refuses blind column drops
--    when pre-migration column ownership is unknown).
-- 3. Never drops any "documents" column or index that already existed prior to this migration
--    (e.g., source_name, source_url, content_hash, embedding, license from out-of-Prisma RAG ingestion).
-- 4. Fails closed (refuses destructive drop) if any newly-added column or newly-created
--    dataset_registry table now holds real post-migration user/enrichment data. See
--    ROLLBACK_AND_RECOVERY.md for non-destructive archive / roll-forward recovery procedures.

DO $$
DECLARE
  ledger_rec RECORD;
  col TEXT;
  idx TEXT;
  candidate_idxs CONSTANT TEXT[] := ARRAY[
    'documents_embedding_hnsw_idx',
    'documents_destination_id_idx',
    'documents_source_name_idx',
    'documents_content_hash_embedding_model_key'
  ];
  has_non_default_data BOOLEAN;
BEGIN
  IF to_regclass(format('%I._migration_20261110_schema_ledger', current_schema())) IS NULL THEN
    RAISE EXCEPTION
      '[C02-F01 FAIL-CLOSED] Missing _migration_20261110_schema_ledger table; refusing automatic rollback because pre-migration RAG column ownership cannot be verified. See ROLLBACK_AND_RECOVERY.md.';
  END IF;

  SELECT *
    INTO ledger_rec
  FROM "_migration_20261110_schema_ledger"
  WHERE "migration_name" = '20261110000000_sync_schema_drift';

  IF NOT FOUND THEN
    RAISE EXCEPTION
      '[C02-F01 FAIL-CLOSED] Missing ledger entry for 20261110000000_sync_schema_drift; refusing automatic column drop. See ROLLBACK_AND_RECOVERY.md.';
  END IF;

  -- Guard 1: Protect newly-created dataset_registry if populated after migration
  IF NOT ledger_rec.dataset_registry_preexisted
     AND to_regclass(format('%I.dataset_registry', current_schema())) IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM "dataset_registry")' INTO has_non_default_data;
    IF has_non_default_data THEN
      RAISE EXCEPTION
        '[C02-F01 FAIL-CLOSED] Refusing to drop newly-created table "dataset_registry" because it contains non-empty governance records. Use roll-forward or archive first per ROLLBACK_AND_RECOVERY.md.';
    END IF;
  END IF;

  -- Guard 2: Check every newly-added "documents" column for post-migration real data
  -- (Pre-existing columns in ledger_rec.preexisting_documents_columns are NEVER dropped.)
  FOREACH col IN ARRAY ledger_rec.added_documents_columns LOOP
    has_non_default_data := FALSE;

    IF col = 'embedding' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "embedding" IS NOT NULL)
        INTO has_non_default_data;
    ELSIF col = 'source_name' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "source_name" <> 'unverified_legacy')
        INTO has_non_default_data;
    ELSIF col = 'source_url' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "source_url" <> '')
        INTO has_non_default_data;
    ELSIF col = 'license' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "license" <> 'UNVERIFIED_LEGACY')
        INTO has_non_default_data;
    ELSIF col = 'attribution' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "attribution" <> '')
        INTO has_non_default_data;
    ELSIF col = 'destination_id' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "destination_id" IS NOT NULL)
        INTO has_non_default_data;
    ELSIF col = 'place_id' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "place_id" IS NOT NULL)
        INTO has_non_default_data;
    ELSIF col = 'topic' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "topic" IS NOT NULL)
        INTO has_non_default_data;
    ELSIF col = 'section_heading' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "section_heading" IS NOT NULL)
        INTO has_non_default_data;
    ELSIF col = 'title' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "title" <> '')
        INTO has_non_default_data;
    ELSIF col = 'document_id' THEN
      SELECT EXISTS (
        SELECT 1 FROM "documents"
        WHERE "document_id" <> ''
          AND "document_id" <> ('legacy-doc-' || "id"::text)
      ) INTO has_non_default_data;
    ELSIF col = 'language' THEN
      SELECT EXISTS (SELECT 1 FROM "documents" WHERE "language" <> 'und')
        INTO has_non_default_data;
    ELSIF col = 'content_hash' THEN
      SELECT EXISTS (
        SELECT 1 FROM "documents"
        WHERE COALESCE(
          CASE
            WHEN "metadata" IS NOT NULL AND jsonb_typeof("metadata") = 'object'
              THEN "metadata"->>'legacy_content_hash_backfilled'
          END,
          'false'
        ) <> 'true'
      ) INTO has_non_default_data;
    ELSIF col = 'embedding_model' THEN
      SELECT EXISTS (
        SELECT 1 FROM "documents"
        WHERE "embedding_model" NOT IN ('unembedded_legacy', 'preexisting_external_embedding')
          AND "embedding_model" <> COALESCE(
            CASE
              WHEN "metadata" IS NOT NULL AND jsonb_typeof("metadata") = 'object'
                THEN btrim("metadata"->>'embedding_model')
            END,
            ''
          )
      ) INTO has_non_default_data;
    END IF;

    IF has_non_default_data THEN
      RAISE EXCEPTION
        '[C02-F01 FAIL-CLOSED] Refusing to drop newly-added column documents.% because non-default RAG data exists. See ROLLBACK_AND_RECOVERY.md for non-destructive recovery.',
        col;
    END IF;
  END LOOP;

  -- Step A: Drop ONLY indexes created by this migration (preserve pre-existing indexes)
  FOREACH idx IN ARRAY candidate_idxs LOOP
    IF NOT (idx = ANY(ledger_rec.preexisting_documents_indexes)) THEN
      EXECUTE format('DROP INDEX IF EXISTS %I', idx);
    END IF;
  END LOOP;

  -- Step B: Drop ONLY columns added by this migration; preserve all pre-existing columns & data
  FOREACH col IN ARRAY ledger_rec.added_documents_columns LOOP
    EXECUTE format('ALTER TABLE "documents" DROP COLUMN IF EXISTS %I', col);
  END LOOP;

  -- Step C: Restore original nullability / default state on pre-existing columns
  FOREACH col IN ARRAY ledger_rec.preexisting_nullable_columns LOOP
    EXECUTE format('ALTER TABLE "documents" ALTER COLUMN %I DROP NOT NULL', col);
  END LOOP;

  FOREACH col IN ARRAY ledger_rec.preexisting_no_default_columns LOOP
    EXECUTE format('ALTER TABLE "documents" ALTER COLUMN %I DROP DEFAULT', col);
  END LOOP;

  FOR col IN SELECT jsonb_object_keys(COALESCE(ledger_rec.preexisting_column_defaults, '{}'::jsonb)) LOOP
    EXECUTE format(
      'ALTER TABLE "documents" ALTER COLUMN %I SET DEFAULT %s',
      col,
      ledger_rec.preexisting_column_defaults->>col
    );
  END LOOP;

  -- Step D: Drop dataset_registry ONLY if created by this migration (already verified empty above)
  IF NOT ledger_rec.dataset_registry_preexisted THEN
    DROP TABLE IF EXISTS "dataset_registry";
  END IF;

  -- Step E: Clean up migration ownership ledger after clean reversal
  DROP TABLE IF EXISTS "_migration_20261110_schema_ledger";
END $$;
