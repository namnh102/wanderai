# Migration `20261110000000_sync_schema_drift` — Non-Destructive Rollback & Recovery Guide

## 1. Historical Context & Hazard Addressed (`C02-F01`)

Prior to `20261110000000_sync_schema_drift`, Prisma's initial migration (`20260922161107_init`) created `"documents"` with only 6 base columns (`id`, `content`, `source`, `category`, `metadata`, `created_at`), while out-of-Prisma RAG ingestion scripts in development/research databases added RAG enrichment columns (`source_name`, `source_url`, `license`, `content_hash`, `embedding`, etc.) directly via raw SQL (as noted in `20261004010000_provenance_remediation/migration.sql`).

Additionally, `"trips"` columns (`currency`, `interests`, `travel_style`) were already introduced by `20261001083200_add_trip_context_fields` and are **not** touched by this migration or its rollback.

A naive `DROP COLUMN IF EXISTS ...` rollback would permanently destroy pre-existing out-of-Prisma RAG enrichment columns and vector embeddings.

## 2. How `migration.sql` and `down.sql` Prevent Data Loss

1. **Pre-Migration Ownership Ledger (`_migration_20261110_schema_ledger`):**
   Before creating `dataset_registry` or adding any column/index to `documents`, `migration.sql` records:
   - `dataset_registry_preexisted`: whether `dataset_registry` existed before migration.
   - `preexisting_documents_columns`: exact RAG columns already present on `documents` before migration.
   - `added_documents_columns`: exact columns newly added by `migration.sql`.
   - `preexisting_nullable_columns` / `preexisting_no_default_columns`: original nullability and default state of pre-existing columns.
   - `preexisting_documents_indexes`: exact indexes already present before migration.
2. **Non-Destructive Selective Reversal:**
   When `down.sql` runs and no post-migration enrichment data was written into `added_documents_columns`:
   - Every column in `preexisting_documents_columns` (such as `source_name`, `source_url`, `license`, `content_hash`, `embedding`) and 100% of its values are **preserved intact**.
   - Only columns in `added_documents_columns` and indexes not in `preexisting_documents_indexes` are dropped, and original nullability/defaults on pre-existing columns are restored.
3. **Fail-Closed Refusal When Destructive Loss Would Occur:**
   `down.sql` aborts inside a single transaction (`RAISE EXCEPTION`) without dropping any column, index, or table whenever:
   - `_migration_20261110_schema_ledger` is missing (unknown column ownership), or
   - Any column in `added_documents_columns` now holds non-default post-migration RAG data (e.g., populated `embedding`, `source_name`, `source_url`, `license`, `attribution`, `place_id`, `title`, etc.), or
   - `dataset_registry` was newly created by this migration and now contains governance records.

## 3. Recommended Production / Research Recovery Procedure (Roll-Forward First)

When `down.sql` aborts fail-closed because real RAG data has been written after migration:

1. **Prefer Roll-Forward Over Destructive Rollback:**
   Keep the schema intact (all columns in `documents` and `dataset_registry` are backward-compatible additions) and deploy a forward fix migration (`prisma migrate deploy`) rather than dropping populated columns.
2. **If Schema Reversal Is Explicitly Required by the Project Owner / DBA:**
   - Take a full verified logical backup first:
     ```bash
     pg_dump --format=custom --file=wanderai_pre_recovery_$(date +%Y%m%d_%H%M%S).dump "$DATABASE_URL"
     ```
   - Export/archive non-default rows from `documents` (and `dataset_registry` if applicable) into an audit backup table in a dedicated archive schema (`CREATE SCHEMA IF NOT EXISTS recovery_archive; CREATE TABLE recovery_archive.documents_snapshot AS SELECT * FROM public.documents;`).
   - Never truncate or drop `documents` columns in place without verified snapshot checksums and explicit Project Owner sign-off.
