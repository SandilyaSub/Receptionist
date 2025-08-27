# Connect Handler Service - Railway Deployment

This is a separate Railway service that handles Exotel Connect applet requests for call handover to human agents.

## Service Architecture

```
Main Service (WebSocket Bridge) → Database → Connect Handler Service
                                     ↓
                              Exotel Connect Applet
```

## Deployment Steps

### 1. Create New Railway Service

1. Go to Railway dashboard
2. Click "New Project" → "Deploy from GitHub repo"
3. Select this repository
4. Choose "Deploy from subdirectory": `connect-service/`

### 2. Environment Variables

Set these environment variables in Railway:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_API_KEY=your_supabase_api_key
DEFAULT_BRANCH_HEAD_PHONE=+919876543210
```

### 3. Railway Configuration

The service includes:
- `railway.json` - Railway deployment configuration
- `requirements.txt` - Python dependencies
- Health check endpoint at `/health`

### 4. Service Endpoints

- **Root**: `GET /` - Service information
- **Connect**: `GET /exotel/connect` - Main Exotel Connect endpoint
- **Health**: `GET /health` - Railway health check

### 5. Exotel Configuration

In your Exotel flow builder:
1. Add Connect Applet after voice bot
2. Set **Dynamic URL**: `https://your-connect-service.railway.app/exotel/connect`
3. Set **Fallback URL**: Same as primary URL

## Testing

Test the service locally:
```bash
cd connect-service
python app.py
```

Test the endpoint:
```bash
curl "http://localhost:5001/exotel/connect?CallSid=test123"
```

## Monitoring

- Railway provides automatic logs and metrics
- Health check endpoint for uptime monitoring
- All handover requests are logged with details

## Integration

The connect handler service:
1. Receives requests from Exotel Connect applet
2. Queries handover details from Supabase
3. Returns formatted phone numbers to Exotel
4. Logs all activities for monitoring
