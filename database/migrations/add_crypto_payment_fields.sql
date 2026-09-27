-- Migration: Add crypto payment fields, subscription revocation, audit indexes
-- Run after: add_manual_payment_support.sql
-- Safe to run multiple times (IF NOT EXISTS)

-- ============================================================
-- 1. Payment table — crypto-specific fields
-- ============================================================
ALTER TABLE payments ADD COLUMN IF NOT EXISTS deposit_address VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS deposit_network VARCHAR(50);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS coin_ticker VARCHAR(10);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS transaction_hash VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS sender_address VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS confirmation_count INTEGER DEFAULT 0;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS expected_amount NUMERIC(20, 8);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS detected_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verification_type VARCHAR(30);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS verified_by VARCHAR(36);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS proof_screenshot_url VARCHAR(500);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS proof_submitted_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS proof_tx_hash VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS proof_amount NUMERIC(20, 8);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS proof_note TEXT;

-- Index for crypto transaction hash lookups
CREATE INDEX IF NOT EXISTS ix_payments_transaction_hash ON payments (transaction_hash);

-- Widen status column to accommodate new crypto states
ALTER TABLE payments ALTER COLUMN status TYPE VARCHAR(40);

-- ============================================================
-- 2. Receipt table — crypto receipt fields
-- ============================================================
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS coin_ticker VARCHAR(10);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS deposit_network VARCHAR(50);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS transaction_hash VARCHAR(255);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS expected_amount NUMERIC(20, 8);
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS paid_amount_crypto NUMERIC(20, 8);

-- ============================================================
-- 3. Subscription table — revocation/suspension fields
-- ============================================================
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS suspension_reason TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS suspended_by VARCHAR(36);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS revoked_by VARCHAR(36);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS revoke_reason TEXT;

-- ============================================================
-- 4. AuditLog indexes (already exists as table)
-- ============================================================
CREATE INDEX IF NOT EXISTS ix_audit_logs_event_type ON audit_logs (event_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);

-- ============================================================
-- Done. All statements are IF NOT EXISTS / safe to re-run.
-- ============================================================
