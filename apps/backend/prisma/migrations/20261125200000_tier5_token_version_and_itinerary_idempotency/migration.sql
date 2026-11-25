-- Tier 5 security & idempotency hardening:
-- 1. Add User.token_version (DEFAULT 0) so password resets atomically revoke prior JWT access/refresh tokens.
-- 2. Add ItineraryItem.client_request_id + unique(itinerary_id, client_request_id) for retry idempotency.

ALTER TABLE "users"
  ADD COLUMN IF NOT EXISTS "token_version" INTEGER NOT NULL DEFAULT 0;

ALTER TABLE "itinerary_items"
  ADD COLUMN IF NOT EXISTS "client_request_id" VARCHAR(128);

CREATE UNIQUE INDEX IF NOT EXISTS "itinerary_items_itinerary_id_client_request_id_key"
  ON "itinerary_items"("itinerary_id", "client_request_id");
