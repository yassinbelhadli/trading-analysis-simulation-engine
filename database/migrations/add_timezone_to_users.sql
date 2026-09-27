-- Add timezone column to users table
-- Default: Africa/Casablanca (the project's default timezone)
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Africa/Casablanca';
