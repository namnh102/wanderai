-- Add destination_id, scope (POI | CITY | NONE), and LINKED_CITY status to youtube_poi_updates
-- for city-level fallback (e.g. Hạ Long) while preserving strict isolation from documents & place_sources.
-- Note: Avoids referencing newly added enum value 'LINKED_CITY' in DML/DEFAULT inside the same transaction (PostgreSQL 55P04).

ALTER TYPE "YoutubeUpdateStatus" ADD VALUE IF NOT EXISTS 'LINKED_CITY';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'YoutubeUpdateScope') THEN
    CREATE TYPE "YoutubeUpdateScope" AS ENUM ('POI', 'CITY', 'NONE');
  END IF;
END $$;

ALTER TABLE "youtube_poi_updates"
  ADD COLUMN IF NOT EXISTS "destination_id" UUID,
  ADD COLUMN IF NOT EXISTS "scope" "YoutubeUpdateScope" NOT NULL DEFAULT 'NONE';

UPDATE "youtube_poi_updates" y
SET
  "scope" = 'POI',
  "destination_id" = COALESCE(y."destination_id", p."destination_id")
FROM "places" p
WHERE y."place_id" = p."id"
  AND y."status" = 'LINKED'
  AND (y."scope" = 'NONE' OR y."destination_id" IS NULL);

CREATE INDEX IF NOT EXISTS "youtube_poi_updates_destination_id_status_scope_published_at_idx"
  ON "youtube_poi_updates"("destination_id", "status", "scope", "published_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'youtube_poi_updates_destination_id_fkey'
  ) THEN
    ALTER TABLE "youtube_poi_updates"
      ADD CONSTRAINT "youtube_poi_updates_destination_id_fkey"
      FOREIGN KEY ("destination_id") REFERENCES "destinations"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
