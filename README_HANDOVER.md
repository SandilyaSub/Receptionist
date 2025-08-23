# Call Handover to Human Agent System

This document describes the implementation of the call handover system that allows the AI receptionist to escalate calls to human agents when needed.

## Architecture Overview

The handover system consists of three main components:

1. **Handover Detection** - Analyzes conversation for escalation requests
2. **Database Storage** - Stores handover details in Supabase
3. **Exotel Connect Integration** - Provides phone numbers for call transfer

## Flow Diagram

```
[Customer Call] → [AI Receptionist] → [Handover Detection] → [Database Storage]
                                                                      ↓
[Human Agent] ← [Exotel Connect] ← [Connect Handler API] ← [Handover Details]
```

## Implementation Details

### 1. Database Schema

Added `call_handover_details` JSONB column to `call_details` table:

```sql
ALTER TABLE call_details 
ADD COLUMN call_handover_details JSONB DEFAULT NULL;
```

**JSON Structure:**
```json
{
  "handover_requested": "yes|no",
  "handover_reason": "escalation|connect_to_manager|could_not_answer|emergency|just_hangup",
  "handover_to": "branch_head|emergency|ambulance",
  "handover_number": "+919876543210"
}
```

### 2. Handover Detection Patterns

The system detects handover requests using regex patterns:

- **Escalation**: "speak to manager", "talk to supervisor", "escalate"
- **Manager Request**: "connect to manager", "transfer to manager"
- **Unable to Answer**: "don't know", "can't help", "need help"
- **Emergency**: "emergency", "urgent", "ambulance"
- **Normal Hangup**: "goodbye", "bye", "thank you"

### 3. Integration Points

#### A. In ExotelGeminiBridge (`new_exotel_bridge.py`)

**Insertion Point**: `_send_coordinated_farewell()` method
- Runs before WebSocket closure
- Gemini session still active for conversation analysis
- Perfect timing to detect handover intent

```python
async def _send_coordinated_farewell(self, farewell_message: str):
    # HANDOVER DETECTION: Analyze conversation before farewell
    await self._analyze_and_store_handover_details()
    # ... rest of farewell logic
```

#### B. Exotel Connect Handler (`exotel_connect_handler.py`)

**Endpoint**: `GET /exotel/connect`
- Called by Exotel's Connect applet after call ends
- Retrieves handover details from database
- Returns phone numbers in Exotel format

### 4. Configuration in Exotel

In your Exotel flow builder:

1. Add a **Connect Applet** after the voice bot
2. Set **Dynamic URL**: `https://your-domain.com/exotel/connect`
3. Configure transitions for successful/failed connections

## Deployment

### 1. Database Migration

Run the SQL migration:
```bash
psql -h your-supabase-host -U postgres -d postgres -f database_migrations/add_handover_details_column.sql
```

### 2. Environment Variables

Add to your environment:
```bash
DEFAULT_BRANCH_HEAD_PHONE=+919876543210  # Fallback number
```

### 3. Start Services

```bash
# Main WebSocket bridge (existing)
python new_exotel_bridge.py

# Connect handler API (new)
python app.py
```

The connect handler runs on port 5001 by default.

### 4. Exotel Configuration

Update your Exotel flow to include:
- **Primary URL**: `https://your-domain.com/exotel/connect`
- **Fallback URL**: `https://your-domain.com/exotel/connect` (same for simplicity)

## Testing

### 1. Test Handover Detection

```bash
# Check if handover details are being stored
curl "https://your-domain.com/exotel/connect?CallSid=test123"
```

### 2. Test Connect Response

Expected response format:
```json
{
  "fetch_after_attempt": false,
  "destination": {
    "numbers": ["+919876543210"]
  },
  "record": true,
  "recording_channels": "dual",
  "max_ringing_duration": 45,
  "max_conversation_duration": 3600,
  "music_on_hold": {
    "type": "operator_tone"
  },
  "start_call_playback": {
    "playback_to": "callee",
    "type": "text",
    "value": "You have a call transfer from our AI assistant..."
  }
}
```

## Monitoring

### 1. Logs to Monitor

- Handover detection: `🔍 Analyzing conversation for handover requests`
- Database storage: `✅ Handover details saved for call_sid`
- Connect requests: `Connect request received - CallSid`

### 2. Database Queries

```sql
-- Check handover requests
SELECT call_sid, call_handover_details 
FROM call_details 
WHERE call_handover_details->>'handover_requested' = 'yes';

-- Handover statistics
SELECT 
  call_handover_details->>'handover_reason' as reason,
  COUNT(*) as count
FROM call_details 
WHERE call_handover_details IS NOT NULL
GROUP BY call_handover_details->>'handover_reason';
```

## Troubleshooting

### Common Issues

1. **No handover details found**
   - Check if conversation analysis is running
   - Verify call_sid is being passed correctly

2. **Connect endpoint not responding**
   - Ensure Flask app is running on port 5001
   - Check firewall/proxy settings

3. **Wrong phone numbers**
   - Verify tenant_configs table has branch_head_phone
   - Check DEFAULT_BRANCH_HEAD_PHONE environment variable

### Debug Mode

Enable detailed logging:
```python
logging.getLogger('handover_service').setLevel(logging.DEBUG)
logging.getLogger('exotel_connect_handler').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Multi-level Escalation**: Support for different agent types
2. **Queue Management**: Integration with agent availability
3. **Analytics Dashboard**: Handover metrics and reporting
4. **Smart Routing**: Route based on query type/complexity
