-- Rollback for 20261126180000_w10_itinerary_voting_and_shared_expenses

DROP TABLE IF EXISTS "settlements";
DROP TABLE IF EXISTS "expense_splits";
DROP TABLE IF EXISTS "expenses";
DROP TABLE IF EXISTS "itinerary_votes";

ALTER TABLE "itinerary_items"
  DROP CONSTRAINT IF EXISTS "itinerary_items_created_by_user_id_fkey";

ALTER TABLE "itinerary_items"
  DROP COLUMN IF EXISTS "created_by_user_id";

DROP TYPE IF EXISTS "SplitType";
DROP TYPE IF EXISTS "ExpenseCategory";
