-- Dynamic Social Freshness Layer: YouTube Update Receiver (`youtube_poi_updates`)
-- Strictly isolated from `documents` (primary RAG corpus) and `place_sources` (POI geographic provenance).
-- Stores UTC TIMESTAMPTZ for both `published_at` (giờ đăng) and `received_at` (giờ nhận).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'YoutubeUpdateStatus') THEN
    CREATE TYPE "YoutubeUpdateStatus" AS ENUM ('LINKED', 'UNLINKED_NO_BASIS');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "youtube_poi_updates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "dedupe_key" VARCHAR(255) NOT NULL,
    "video_id" VARCHAR(32) NOT NULL,
    "channel_id" VARCHAR(64) NOT NULL,
    "channel_title" VARCHAR(255),
    "video_url" VARCHAR(500) NOT NULL,
    "title" VARCHAR(500) NOT NULL,
    "description" TEXT,
    "tags" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "published_at" TIMESTAMPTZ NOT NULL,
    "source_updated_at" TIMESTAMPTZ,
    "received_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_received_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "delivery_count" INTEGER NOT NULL DEFAULT 1,
    "status" "YoutubeUpdateStatus" NOT NULL DEFAULT 'UNLINKED_NO_BASIS',
    "place_id" UUID,
    "grounding_basis" VARCHAR(100),
    "decision_reason" VARCHAR(120) NOT NULL,
    "grounding_evidence" JSONB,
    "raw_payload" JSONB,

    CONSTRAINT "youtube_poi_updates_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "youtube_poi_updates_dedupe_key_key"
    ON "youtube_poi_updates"("dedupe_key");

CREATE INDEX IF NOT EXISTS "youtube_poi_updates_place_id_status_published_at_idx"
    ON "youtube_poi_updates"("place_id", "status", "published_at" DESC);

CREATE INDEX IF NOT EXISTS "youtube_poi_updates_video_id_published_at_idx"
    ON "youtube_poi_updates"("video_id", "published_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'youtube_poi_updates_place_id_fkey'
  ) THEN
    ALTER TABLE "youtube_poi_updates"
      ADD CONSTRAINT "youtube_poi_updates_place_id_fkey"
      FOREIGN KEY ("place_id") REFERENCES "places"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
