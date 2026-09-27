-- Migration: Allow subscription history
-- Remove UNIQUE constraint on subscriptions.user_id
-- Add partial unique index: only one ACTIVE subscription per user
-- Add created_at column for ordering historical subscriptions

-- 1. Drop the existing unique constraint
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_user_id_key;

-- 2. Add partial unique index: at most one active subscription per user
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_subscription
  ON subscriptions (user_id)
  WHERE active = true;

-- 3. Add created_at column for subscription ordering (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'created_at') THEN
    ALTER TABLE subscriptions ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
    -- Backfill existing rows
    UPDATE subscriptions SET created_at = start_date WHERE created_at IS NULL;
  END IF;
END
$$;
