-- W08 Buddy Matching: Explicit opt-in consent, invitation withdrawal, and two-way user blocking
ALTER TYPE "MatchStatus" ADD VALUE IF NOT EXISTS 'WITHDRAWN';

ALTER TABLE "profiles"
  ADD COLUMN IF NOT EXISTS "is_discoverable" BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE "matches"
  ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS "matches_status_idx" ON "matches"("status");

CREATE TABLE IF NOT EXISTS "user_blocks" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "blocker_id" UUID NOT NULL,
  "blocked_id" UUID NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "user_blocks_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "user_blocks_blocker_id_blocked_id_key"
  ON "user_blocks"("blocker_id", "blocked_id");

CREATE INDEX IF NOT EXISTS "user_blocks_blocked_id_idx"
  ON "user_blocks"("blocked_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_blocks_blocker_id_fkey'
  ) THEN
    ALTER TABLE "user_blocks"
      ADD CONSTRAINT "user_blocks_blocker_id_fkey"
      FOREIGN KEY ("blocker_id") REFERENCES "users"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_blocks_blocked_id_fkey'
  ) THEN
    ALTER TABLE "user_blocks"
      ADD CONSTRAINT "user_blocks_blocked_id_fkey"
      FOREIGN KEY ("blocked_id") REFERENCES "users"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;
