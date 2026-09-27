-- Migration: multi-currency Plans + Subscriptions + Coupons
-- Applies manual column additions (project convention: create_all for new
-- tables, manual ALTER TABLE for column additions).
--
-- coupons / coupon_redemptions tables are created automatically by
-- Base.metadata.create_all() — no DDL needed here for them.

-- PlanDefinition: multi-currency pricing + presentation fields
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS price_usd NUMERIC(10,2);
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS price_eur NUMERIC(10,2);
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS price_mad NUMERIC(10,2);
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS duration_days INTEGER DEFAULT 30;
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS features_json JSONB DEFAULT '{}';
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS badge VARCHAR(100);
ALTER TABLE plan_definitions ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;

-- Subscription: snapshot fields (preserve what was purchased)
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_name VARCHAR(100);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_description TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_duration_days INTEGER;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_price_paid NUMERIC(10,2);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_currency VARCHAR(3);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_features JSONB;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10,2);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS subscription_number VARCHAR(20) UNIQUE;

-- User: client's preferred billing currency
ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_currency VARCHAR(3);
