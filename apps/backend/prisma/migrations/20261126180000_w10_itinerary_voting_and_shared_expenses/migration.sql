-- W10 MVP: Group Itinerary Voting (WP-ITIN-01) & Shared Expenses / Settlements (WP-EXP-01, WP-EXP-02)
-- Fully idempotent migration SQL.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ExpenseCategory') THEN
    CREATE TYPE "ExpenseCategory" AS ENUM (
      'FOOD',
      'TRANSPORT',
      'ACCOMMODATION',
      'TICKET',
      'SHOPPING',
      'OTHER'
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'SplitType') THEN
    CREATE TYPE "SplitType" AS ENUM ('EQUAL', 'CUSTOM');
  END IF;
END $$;

ALTER TABLE "itinerary_items"
  ADD COLUMN IF NOT EXISTS "created_by_user_id" UUID;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'itinerary_items_created_by_user_id_fkey'
  ) THEN
    ALTER TABLE "itinerary_items"
      ADD CONSTRAINT "itinerary_items_created_by_user_id_fkey"
      FOREIGN KEY ("created_by_user_id") REFERENCES "users"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "itinerary_votes" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "item_id" UUID NOT NULL,
  "user_id" UUID NOT NULL,
  "vote" BOOLEAN NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "itinerary_votes_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "itinerary_votes_item_id_user_id_key"
  ON "itinerary_votes"("item_id", "user_id");

CREATE INDEX IF NOT EXISTS "itinerary_votes_user_id_idx"
  ON "itinerary_votes"("user_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'itinerary_votes_item_id_fkey'
  ) THEN
    ALTER TABLE "itinerary_votes"
      ADD CONSTRAINT "itinerary_votes_item_id_fkey"
      FOREIGN KEY ("item_id") REFERENCES "itinerary_items"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'itinerary_votes_user_id_fkey'
  ) THEN
    ALTER TABLE "itinerary_votes"
      ADD CONSTRAINT "itinerary_votes_user_id_fkey"
      FOREIGN KEY ("user_id") REFERENCES "users"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "expenses" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "group_id" UUID NOT NULL,
  "trip_id" UUID,
  "paid_by_user_id" UUID NOT NULL,
  "created_by_user_id" UUID NOT NULL,
  "client_request_id" VARCHAR(128),
  "title" VARCHAR(200) NOT NULL,
  "amount" INTEGER NOT NULL,
  "currency" VARCHAR(10) NOT NULL DEFAULT 'VND',
  "category" "ExpenseCategory" NOT NULL DEFAULT 'OTHER',
  "split_type" "SplitType" NOT NULL DEFAULT 'EQUAL',
  "expense_date" DATE NOT NULL DEFAULT CURRENT_DATE,
  "notes" TEXT,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" TIMESTAMPTZ,
  CONSTRAINT "expenses_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "expenses_group_id_client_request_id_key"
  ON "expenses"("group_id", "client_request_id");

CREATE INDEX IF NOT EXISTS "expenses_group_id_deleted_at_idx"
  ON "expenses"("group_id", "deleted_at");

CREATE INDEX IF NOT EXISTS "expenses_trip_id_idx"
  ON "expenses"("trip_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expenses_amount_positive_chk'
  ) THEN
    ALTER TABLE "expenses"
      ADD CONSTRAINT "expenses_amount_positive_chk" CHECK ("amount" > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expenses_group_id_fkey'
  ) THEN
    ALTER TABLE "expenses"
      ADD CONSTRAINT "expenses_group_id_fkey"
      FOREIGN KEY ("group_id") REFERENCES "groups"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expenses_trip_id_fkey'
  ) THEN
    ALTER TABLE "expenses"
      ADD CONSTRAINT "expenses_trip_id_fkey"
      FOREIGN KEY ("trip_id") REFERENCES "trips"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expenses_paid_by_user_id_fkey'
  ) THEN
    ALTER TABLE "expenses"
      ADD CONSTRAINT "expenses_paid_by_user_id_fkey"
      FOREIGN KEY ("paid_by_user_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expenses_created_by_user_id_fkey'
  ) THEN
    ALTER TABLE "expenses"
      ADD CONSTRAINT "expenses_created_by_user_id_fkey"
      FOREIGN KEY ("created_by_user_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "expense_splits" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "expense_id" UUID NOT NULL,
  "user_id" UUID NOT NULL,
  "share_amount" INTEGER NOT NULL,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "expense_splits_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "expense_splits_expense_id_user_id_key"
  ON "expense_splits"("expense_id", "user_id");

CREATE INDEX IF NOT EXISTS "expense_splits_user_id_idx"
  ON "expense_splits"("user_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expense_splits_share_amount_positive_chk'
  ) THEN
    ALTER TABLE "expense_splits"
      ADD CONSTRAINT "expense_splits_share_amount_positive_chk" CHECK ("share_amount" > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expense_splits_expense_id_fkey'
  ) THEN
    ALTER TABLE "expense_splits"
      ADD CONSTRAINT "expense_splits_expense_id_fkey"
      FOREIGN KEY ("expense_id") REFERENCES "expenses"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'expense_splits_user_id_fkey'
  ) THEN
    ALTER TABLE "expense_splits"
      ADD CONSTRAINT "expense_splits_user_id_fkey"
      FOREIGN KEY ("user_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "settlements" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "group_id" UUID NOT NULL,
  "trip_id" UUID,
  "debtor_id" UUID NOT NULL,
  "creditor_id" UUID NOT NULL,
  "created_by_user_id" UUID NOT NULL,
  "client_request_id" VARCHAR(128),
  "amount" INTEGER NOT NULL,
  "currency" VARCHAR(10) NOT NULL DEFAULT 'VND',
  "notes" TEXT,
  "settled_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "settlements_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "settlements_group_id_client_request_id_key"
  ON "settlements"("group_id", "client_request_id");

CREATE INDEX IF NOT EXISTS "settlements_group_id_settled_at_idx"
  ON "settlements"("group_id", "settled_at");

CREATE INDEX IF NOT EXISTS "settlements_trip_id_idx"
  ON "settlements"("trip_id");

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_amount_positive_chk'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_amount_positive_chk" CHECK ("amount" > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_distinct_parties_chk'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_distinct_parties_chk" CHECK ("debtor_id" <> "creditor_id");
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_group_id_fkey'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_group_id_fkey"
      FOREIGN KEY ("group_id") REFERENCES "groups"("id")
      ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_trip_id_fkey'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_trip_id_fkey"
      FOREIGN KEY ("trip_id") REFERENCES "trips"("id")
      ON DELETE SET NULL ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_debtor_id_fkey'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_debtor_id_fkey"
      FOREIGN KEY ("debtor_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_creditor_id_fkey'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_creditor_id_fkey"
      FOREIGN KEY ("creditor_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'settlements_created_by_user_id_fkey'
  ) THEN
    ALTER TABLE "settlements"
      ADD CONSTRAINT "settlements_created_by_user_id_fkey"
      FOREIGN KEY ("created_by_user_id") REFERENCES "users"("id")
      ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;
END $$;
