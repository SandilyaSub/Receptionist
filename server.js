
const WebSocket = require('ws');
const https = require('https');

// Use Railway's PORT environment variable, fallback to 8080 for local development
const PORT = process.env.PORT || 8080;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

if (!OPENAI_API_KEY) {
  console.error('ERROR: OPENAI_API_KEY environment variable is required');
  process.exit(1);
}

console.log('Starting Bakery Bot WebSocket Server...');

// Create WebSocket server - listen on all interfaces for Railway
const wss = new WebSocket.Server({ 
  port: PORT,
  host: '0.0.0.0'
});

console.log(`Bakery Bot WebSocket Server running on port ${PORT}`);
console.log('Server is ready to accept connections');

// Handle new WebSocket connections
wss.on('connection', (ws, req) => {
  console.log('New client connected from:', req.socket.remoteAddress);
  
  let openaiWs = null;
  
  // Connect to OpenAI Realtime API
  const connectToOpenAI = () => {
    const url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01';
    
    openaiWs = new WebSocket(url, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'OpenAI-Beta': 'realtime=v1'
      }
    });
    
    openaiWs.on('open', () => {
      console.log('Connected to OpenAI Realtime API');
      
      // Send session configuration
      const sessionConfig = {
        type: 'session.update',
        session: {
          modalities: ['text', 'audio'],
          instructions: 'You are a helpful bakery assistant. Help customers with their orders and questions about baked goods.',
          voice: 'alloy',
          input_audio_format: 'pcm16',
          output_audio_format: 'pcm16',
          input_audio_transcription: {
            model: 'whisper-1'
          }
        }
      };
      
      openaiWs.send(JSON.stringify(sessionConfig));
    });
    
    openaiWs.on('message', (data) => {
      // Forward OpenAI messages to client
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });
    
    openaiWs.on('error', (error) => {
      console.error('OpenAI WebSocket error:', error);
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'error',
          message: 'OpenAI connection error'
        }));
      }
    });
    
    openaiWs.on('close', () => {
      console.log('OpenAI WebSocket closed');
    });
  };
  
  // Connect to OpenAI when client connects
  connectToOpenAI();
  
  // Handle messages from client (Exotel)
  ws.on('message', (message) => {
    console.log('Received from client:', message.toString());
    
    try {
      // Forward client messages to OpenAI
      if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
        openaiWs.send(message);
      }
    } catch (error) {
      console.error('Error forwarding message to OpenAI:', error);
    }
  });
  
  // Handle client disconnection
  ws.on('close', () => {
    console.log('Client disconnected');
    if (openaiWs) {
      openaiWs.close();
    }
  });
  
  // Handle client errors
  ws.on('error', (error) => {
    console.error('Client WebSocket error:', error);
  });
});

// Handle server errors
wss.on('error', (error) => {
  console.error('WebSocket server error:', error);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down gracefully');
  wss.close();
});

process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down gracefully');
  wss.close();
});
