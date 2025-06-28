# Receptionist Lovable - Exotel/Gemini Bridge

This project provides a WebSocket bridge to connect Exotel's voice streaming service with Google's Gemini Live API for a real-time conversational AI receptionist.

## Setup and Configuration

### 1. Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Your Gemini API key must be set as an environment variable.
```bash
export GEMINI_API_KEY='YOUR_API_KEY_HERE'
```
Alternatively, you can create a `.env` file in the root directory and add the key there:
```
GEMINI_API_KEY='YOUR_API_KEY_HERE'
```

### 3. Gemini Model Configuration
The only supported model for this project is `models/gemini-2.5-flash-preview-native-audio-dialog`. This is configured within `new_exotel_bridge.py`.

## Running the Server

### Local Development
To start the WebSocket bridge server locally, run:
```bash
python3 new_exotel_bridge.py
```
The server will start on port 8765 by default.

### Railway Deployment

This project is configured for deployment on Railway. Follow these steps to deploy:

1. **Create a Railway account** at [railway.app](https://railway.app) if you don't have one already.

2. **Install the Railway CLI** (optional but recommended):
   ```bash
   npm i -g @railway/cli
   ```

3. **Login to Railway**:
   ```bash
   railway login
   ```

4. **Create a new project** in Railway dashboard or via CLI:
   ```bash
   railway init
   ```

5. **Set environment variables** in the Railway dashboard:
   - `GEMINI_API_KEY`: Your Google Gemini API key

6. **Deploy the application**:
   ```bash
   railway up
   ```

7. **Configure Exotel** to connect to your Railway deployment URL:
   - Railway will provide you with a domain (e.g., `https://your-app-name.up.railway.app`)
   - In Exotel, configure the WebSocket endpoint as `wss://your-app-name.up.railway.app/media`

### WebSocket Secure (WSS)

Railway automatically provides SSL/TLS termination, so your application will be accessible via WSS (WebSocket Secure) without any additional configuration. This is required for production use with Exotel.
