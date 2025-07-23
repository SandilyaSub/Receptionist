-- Migration to add AI token usage tracking to call_details table
-- Run this in your Supabase SQL editor

-- Add ai_token_usage column to call_details table
ALTER TABLE call_details 
ADD COLUMN IF NOT EXISTS ai_token_usage JSONB NULL;

-- Add a comment to document the column
COMMENT ON COLUMN call_details.ai_token_usage IS 'JSON object containing AI token usage data for conversation, transcript analysis, and WhatsApp generation';

-- Example of the JSON structure that will be stored:
-- {
--   "conversation": {
--     "model": "gemini-2.0-flash-exp",
--     "total_tokens": 15420,
--     "input_tokens": 8500,
--     "output_tokens": 6920
--   },
--   "transcript_analysis": {
--     "model": "gemini-2.5-flash",
--     "total_tokens": 2139,
--     "prompt_tokens": 1719,
--     "candidates_tokens": 121,
--     "thoughts_tokens": 299
--   },
--   "whatsapp_generation": {
--     "model": "gemini-2.5-flash", 
--     "total_tokens": 1856,
--     "prompt_tokens": 1623,
--     "candidates_tokens": 137,
--     "thoughts_tokens": 96
--   },
--   "total_tokens_all_operations": 19415
-- }
