-- Rollback for 20261125180000_add_youtube_destination_and_scope
-- Note: PostgreSQL retains enum label 'LINKED_CITY' on "YoutubeUpdateStatus" unless the enum type is recreated.

UPDATE "youtube_poi_updates"
SET "status" = 'UNLINKED_NO_BASIS'
WHERE "status"::text = 'LINKED_CITY';

ALTER TABLE "youtube_poi_updates"
  DROP CONSTRAINT IF EXISTS "youtube_poi_updates_destination_id_fkey";

DROP INDEX IF EXISTS "youtube_poi_updates_destination_id_status_scope_published_at_idx";

ALTER TABLE "youtube_poi_updates"
  DROP COLUMN IF EXISTS "scope",
  DROP COLUMN IF EXISTS "destination_id";

DROP TYPE IF EXISTS "YoutubeUpdateScope";
