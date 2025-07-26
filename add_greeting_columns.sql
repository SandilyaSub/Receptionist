-- Migration script to add greeting columns to tenant_configs table
-- Run this in your Supabase SQL editor

-- Add the new columns to tenant_configs table
ALTER TABLE tenant_configs 
ADD COLUMN IF NOT EXISTS language text DEFAULT 'english',
ADD COLUMN IF NOT EXISTS welcome_message text DEFAULT NULL;

-- Update existing records with default values if needed
UPDATE tenant_configs 
SET language = 'english' 
WHERE language IS NULL;

-- Add some sample data for testing
UPDATE tenant_configs 
SET welcome_message = 'Welcome to Happy Endings Bakery! My name is Aarohi, your virtual assistant. How may I help you today?',
    language = 'english'
WHERE tenant_id = 'bakery';

UPDATE tenant_configs 
SET welcome_message = 'Welcome to Glamour Salon! I am Aarohi, your virtual receptionist. How can I assist you today?',
    language = 'english'  
WHERE tenant_id = 'saloon';

-- Verify the changes
SELECT tenant_id, language, welcome_message FROM tenant_configs;
