-- Add handover_details column to call_details table
-- This column stores JSON data about call handover requests

ALTER TABLE call_details 
ADD COLUMN call_handover_details JSONB DEFAULT NULL;

-- Add index for efficient querying of handover requests
CREATE INDEX idx_call_details_handover_requested 
ON call_details USING GIN ((call_handover_details->>'handover_requested'));

-- Add comment for documentation
COMMENT ON COLUMN call_details.call_handover_details IS 'JSON blob containing handover details: handover_requested, handover_reason, handover_to, handover_number';
