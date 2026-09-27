-- Migration: Add payment_method_configs table for owner-configurable payment instructions.
CREATE TABLE IF NOT EXISTS payment_method_configs (
    id VARCHAR(36) PRIMARY KEY,
    method_id VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    beneficiary_name VARCHAR(200),
    account_rib VARCHAR(100),
    phone_number VARCHAR(50),
    branch VARCHAR(200),
    instructions TEXT,
    reference_instructions TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
