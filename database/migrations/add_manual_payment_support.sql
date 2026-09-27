-- Migration: Add manual payment support + payment method routing
-- Adds fields for manual payment workflow (Cash Plus, Chaabi Cash, Tashilat)
-- Adds payment_method_type for automatic vs manual classification

-- 1. Add payment_method_type column (automatic | manual)
ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_method_type VARCHAR(20) NULL;

-- 2. Add manual payment fields
ALTER TABLE payments ADD COLUMN IF NOT EXISTS manual_reference VARCHAR(255) NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS manual_proof_url VARCHAR(500) NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS manual_instructions TEXT NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS approved_by VARCHAR(36) NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(500) NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS internal_notes TEXT NULL;

-- 3. Widen status column from VARCHAR(20) to VARCHAR(30) for PENDING_VERIFICATION
ALTER TABLE payments ALTER COLUMN status TYPE VARCHAR(30);

-- 4. Add foreign key for approved_by (references users.id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_payments_approved_by'
    ) THEN
        ALTER TABLE payments
            ADD CONSTRAINT fk_payments_approved_by
            FOREIGN KEY (approved_by) REFERENCES users(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 5. Add indexes for manual payment queries
CREATE INDEX IF NOT EXISTS idx_payments_method_type ON payments(payment_method_type);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_approved_by ON payments(approved_by) WHERE approved_by IS NOT NULL;

-- 6. Backfill existing payments with payment_method_type = 'automatic'
UPDATE payments SET payment_method_type = 'automatic' WHERE payment_method_type IS NULL;
