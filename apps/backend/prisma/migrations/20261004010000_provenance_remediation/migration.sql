-- TASK 07.3: provenance & data integrity remediation.
-- Schema part + idempotent data remediation (safe on a fresh database: every data step is a no-op when empty).

-- ============ SCHEMA ============
-- 1. A missing rating is NULL, never a fabricated default.
ALTER TABLE "places" ALTER COLUMN "rating" DROP NOT NULL;
ALTER TABLE "places" ALTER COLUMN "rating" DROP DEFAULT;

-- 2. Reviews carry a provenance label.
ALTER TABLE "reviews" ADD COLUMN "source" VARCHAR(20) NOT NULL DEFAULT 'user';
ALTER TABLE "reviews" ADD COLUMN "trusted" BOOLEAN NOT NULL DEFAULT true;

-- 3. Audit-trail tables (nothing is deleted without a copy).
CREATE TABLE "place_source_quarantine" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "original_id" UUID NOT NULL,
    "place_id" UUID NOT NULL,
    "source_name" VARCHAR(50) NOT NULL,
    "source_id" VARCHAR(255) NOT NULL,
    "raw_name" VARCHAR(255) NOT NULL,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "raw_data" JSONB,
    "reason" VARCHAR(100) NOT NULL,
    "evidence" JSONB,
    "quarantined_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "place_source_quarantine_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "place_source_quarantine_place_id_idx" ON "place_source_quarantine"("place_id");

CREATE TABLE "document_quarantine" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "original_id" UUID NOT NULL,
    "row_data" JSONB NOT NULL,
    "reason" VARCHAR(100) NOT NULL,
    "quarantined_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "document_quarantine_pkey" PRIMARY KEY ("id")
);

-- ============ DATA REMEDIATION ============
-- A. 11 OSM sources that do not exist upstream or point to an unrelated object
--    (independently checked against the Overpass API on 2026-10-03; see
--    docs/audit/task-07.3-provenance-remediation.md and data/manifests/osm-invalid-sources.json).
--    No replacement ids are invented: the source rows are moved to the quarantine table.
INSERT INTO "place_source_quarantine"
    ("original_id","place_id","source_name","source_id","raw_name","latitude","longitude","raw_data","reason","evidence")
SELECT ps."id", ps."place_id", ps."source_name", ps."source_id", ps."raw_name", ps."latitude", ps."longitude", ps."raw_data",
       CASE WHEN ps."source_id" IN ('node/192837465','node/348291039','node/564738291','node/789456123','node/859302194')
            THEN 'osm_id_points_to_unrelated_object' ELSE 'osm_id_not_found_upstream' END,
       jsonb_build_object('verified_with','Overpass API','verified_on','2026-10-03',
                          'stored_name', ps."raw_name", 'stored_lat', ps."latitude", 'stored_lon', ps."longitude")
FROM "place_sources" ps
WHERE ps."source_name" = 'osm'
  AND ps."source_id" IN ('node/192837465','node/348291039','node/564738291','node/789456123','node/859302194',
                         'node/1459203941','node/268491823','node/675849302','node/890123456','node/901234567','node/923847291');

DELETE FROM "place_sources"
WHERE "source_name" = 'osm'
  AND "source_id" IN ('node/192837465','node/348291039','node/564738291','node/789456123','node/859302194',
                      'node/1459203941','node/268491823','node/675849302','node/890123456','node/901234567','node/923847291');

-- B. Reviews written by the seed/fixture accounts are synthetic and untrusted.
UPDATE "reviews" SET "source" = 'synthetic', "trusted" = false
WHERE "user_id" IN (SELECT "id" FROM "users" WHERE "email" IN ('curator@wanderai.vn', 'test@wanderai.test', 'test@wanderai.vn'));

-- C. Ratings are derived only from trusted, non-deleted reviews; otherwise NULL (never 0, never 4.5).
UPDATE "places" p SET
    "rating" = (SELECT round(avg(r."rating")::numeric, 1)::double precision
                FROM "reviews" r WHERE r."place_id" = p."id" AND r."trusted" AND r."deleted_at" IS NULL),
    "review_count" = (SELECT count(*)::int
                      FROM "reviews" r WHERE r."place_id" = p."id" AND r."trusted" AND r."deleted_at" IS NULL);

-- D. RAG chunks attached to places that have no verified source are not OSM-derived knowledge:
--    copy them (without the embedding vector) to document_quarantine and remove them from retrieval.
--    `documents` columns were added outside Prisma migrations, so guard on the column existing.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'place_id') THEN
        INSERT INTO "document_quarantine" ("original_id", "row_data", "reason")
        SELECT d."id", to_jsonb(d) - 'embedding', 'chunk_linked_to_place_without_verified_source'
        FROM "documents" d
        WHERE d."place_id" IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM "place_sources" ps WHERE ps."place_id" = d."place_id");

        DELETE FROM "documents" d
        WHERE d."place_id" IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM "place_sources" ps WHERE ps."place_id" = d."place_id");
    END IF;
END $$;
