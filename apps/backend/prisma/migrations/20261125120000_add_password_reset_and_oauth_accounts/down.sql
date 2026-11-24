-- Rollback for 20261125120000_add_password_reset_and_oauth_accounts
-- Note: users.password_hash is left nullable if OAuth-only rows exist; restore NOT NULL only when no NULL rows remain.

DROP TABLE IF EXISTS "oauth_accounts";
DROP TABLE IF EXISTS "password_reset_tokens";
DROP TYPE IF EXISTS "OAuthProvider";

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "users" WHERE "password_hash" IS NULL) THEN
    ALTER TABLE "users" ALTER COLUMN "password_hash" SET NOT NULL;
  END IF;
END $$;
