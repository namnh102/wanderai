-- Trip Invitations & In-App Notification Consent Flow
-- Fully idempotent migration SQL.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'TripInviteStatus') THEN
    CREATE TYPE "TripInviteStatus" AS ENUM (
      'PENDING',
      'ACCEPTED',
      'DECLINED',
      'REVOKED'
    );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "trip_invites" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "trip_id" UUID NOT NULL,
  "inviter_id" UUID NOT NULL,
  "invitee_id" UUID NOT NULL,
  "notification_id" UUID,
  "status" "TripInviteStatus" NOT NULL DEFAULT 'PENDING',
  "responded_at" TIMESTAMPTZ,
  "revoked_at" TIMESTAMPTZ,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "trip_invites_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "trip_invites_notification_id_key"
  ON "trip_invites"("notification_id");

CREATE UNIQUE INDEX IF NOT EXISTS "trip_invites_pending_unique_idx"
  ON "trip_invites"("trip_id", "invitee_id")
  WHERE "status" = 'PENDING';

CREATE INDEX IF NOT EXISTS "trip_invites_invitee_id_status_created_at_idx"
  ON "trip_invites"("invitee_id", "status", "created_at" DESC);

CREATE INDEX IF NOT EXISTS "trip_invites_trip_id_status_idx"
  ON "trip_invites"("trip_id", "status");

CREATE INDEX IF NOT EXISTS "notifications_user_id_is_read_created_at_idx"
  ON "notifications"("user_id", "is_read", "created_at" DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trip_invites_trip_id_fkey'
  ) THEN
    ALTER TABLE "trip_invites"
      ADD CONSTRAINT "trip_invites_trip_id_fkey"
      FOREIGN KEY ("trip_id") REFERENCES "trips"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trip_invites_inviter_id_fkey'
  ) THEN
    ALTER TABLE "trip_invites"
      ADD CONSTRAINT "trip_invites_inviter_id_fkey"
      FOREIGN KEY ("inviter_id") REFERENCES "users"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trip_invites_invitee_id_fkey'
  ) THEN
    ALTER TABLE "trip_invites"
      ADD CONSTRAINT "trip_invites_invitee_id_fkey"
      FOREIGN KEY ("invitee_id") REFERENCES "users"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trip_invites_notification_id_fkey'
  ) THEN
    ALTER TABLE "trip_invites"
      ADD CONSTRAINT "trip_invites_notification_id_fkey"
      FOREIGN KEY ("notification_id") REFERENCES "notifications"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;
