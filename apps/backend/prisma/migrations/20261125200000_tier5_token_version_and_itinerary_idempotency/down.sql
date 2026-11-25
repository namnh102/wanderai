-- Rollback for 20261125200000_tier5_token_version_and_itinerary_idempotency

DROP INDEX IF EXISTS "itinerary_items_itinerary_id_client_request_id_key";

ALTER TABLE "itinerary_items"
  DROP COLUMN IF EXISTS "client_request_id";

ALTER TABLE "users"
  DROP COLUMN IF EXISTS "token_version";
