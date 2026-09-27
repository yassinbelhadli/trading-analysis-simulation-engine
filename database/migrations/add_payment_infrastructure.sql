-- Payment Infrastructure Migration
-- Creates payments, receipts tables and adds status column to subscriptions.
-- Run with: psql -U postgres -d ict_funded_ea -f add_payment_infrastructure.sql

-- Add status column to subscriptions (default ACTIVE for existing rows)
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions(status);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id VARCHAR(36) PRIMARY KEY,
    payment_number VARCHAR(20) UNIQUE NOT NULL,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    subscription_id VARCHAR(36) REFERENCES subscriptions(id),
    plan_id VARCHAR(50) NOT NULL REFERENCES plan_definitions(id),
    coupon_id VARCHAR(36) REFERENCES coupons(id),
    original_amount NUMERIC(10, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
    final_amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_provider VARCHAR(30) NOT NULL DEFAULT 'none',
    provider_payment_id VARCHAR(255),
    provider_checkout_id VARCHAR(255),
    payment_method VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    failure_reason TEXT,
    plan_name VARCHAR(100),
    plan_duration_days INTEGER,
    coupon_code VARCHAR(50),
    provider_event_id VARCHAR(255),
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    refunded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS ix_payments_subscription_id ON payments(subscription_id);
CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS ix_payments_created_at ON payments(created_at);
CREATE INDEX IF NOT EXISTS ix_payments_provider_payment_id ON payments(provider_payment_id);
CREATE INDEX IF NOT EXISTS ix_payments_provider_checkout_id ON payments(provider_checkout_id);
CREATE INDEX IF NOT EXISTS ix_payments_provider_event_id ON payments(provider_event_id);

-- Receipts table
CREATE TABLE IF NOT EXISTS receipts (
    id VARCHAR(36) PRIMARY KEY,
    receipt_number VARCHAR(20) UNIQUE NOT NULL,
    payment_id VARCHAR(36) NOT NULL REFERENCES payments(id),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    subscription_id VARCHAR(36) REFERENCES subscriptions(id),
    plan_name VARCHAR(100) NOT NULL,
    plan_duration_days INTEGER,
    original_amount NUMERIC(10, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
    final_amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    coupon_code VARCHAR(50),
    payment_method VARCHAR(50),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PAID',
    paid_at TIMESTAMPTZ NOT NULL,
    subscription_start TIMESTAMPTZ,
    subscription_expiration TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_receipts_payment_id ON receipts(payment_id);
CREATE INDEX IF NOT EXISTS ix_receipts_user_id ON receipts(user_id);
CREATE INDEX IF NOT EXISTS ix_receipts_receipt_number ON receipts(receipt_number);
