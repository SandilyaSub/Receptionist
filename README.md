
# Bakery Bot WebSocket Server

A WebSocket server that connects Exotel phone calls to OpenAI's Realtime API for a bakery assistant bot.

## Features

- WebSocket server for real-time communication
- Integration with OpenAI Realtime API
- Bakery-specific assistant configuration
- Audio streaming support
- Error handling and reconnection logic

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `PORT` - Server port (default: 3000)

## Local Development

1. Install dependencies:
   ```bash
   npm install
   ```

2. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

3. Start the server:
   ```bash
   npm start
   ```

## Deployment

This server is designed to be deployed on Railway, Render, or similar platforms that support WebSocket connections.

## WebSocket URL

After deployment, your WebSocket URL will be:
`wss://your-app-name.railway.app`

Configure this URL in your Exotel webhook settings.
