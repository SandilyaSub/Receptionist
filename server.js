
const WebSocket = require('ws');
const http = require('http');
const OpenAI = require('openai');

// Configuration
const PORT = process.env.PORT || 3000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

if (!OPENAI_API_KEY) {
  console.error('OPENAI_API_KEY environment variable is required');
  process.exit(1);
}

const openai = new OpenAI({
  apiKey: OPENAI_API_KEY,
});

// Create HTTP server
const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Bakery Bot WebSocket Server is running!');
});

// Create WebSocket server
const wss = new WebSocket.Server({ server });

console.log('Starting Bakery Bot WebSocket Server...');

wss.on('connection', (ws, req) => {
  console.log('New WebSocket connection from:', req.socket.remoteAddress);
  
  let openaiWs = null;
  
  // Initialize OpenAI WebSocket connection
  const initOpenAI = () => {
    try {
      openaiWs = new WebSocket('wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01', {
        headers: {
          'Authorization': `Bearer ${OPENAI_API_KEY}`,
          'OpenAI-Beta': 'realtime=v1',
        },
      });

      openaiWs.on('open', () => {
        console.log('Connected to OpenAI Realtime API');
        
        // Configure the session for bakery bot
        const sessionConfig = {
          type: 'session.update',
          session: {
            modalities: ['text', 'audio'],
            instructions: `You are a helpful bakery assistant. Help customers with:
            - Taking orders for baked goods
            - Providing information about menu items
            - Answering questions about ingredients and allergens
            - Store hours and location
            - Custom cake orders
            
            Be friendly, professional, and concise. If you can't help with something, politely direct them to call the bakery directly.`,
            voice: 'alloy',
            input_audio_format: 'pcm16',
            output_audio_format: 'pcm16',
            turn_detection: {
              type: 'server_vad',
              threshold: 0.5,
              prefix_padding_ms: 300,
              silence_duration_ms: 200,
            },
          },
        };
        
        openaiWs.send(JSON.stringify(sessionConfig));
      });

      openaiWs.on('message', (data) => {
        try {
          const message = JSON.parse(data);
          console.log('OpenAI message type:', message.type);
          
          // Forward OpenAI responses to Exotel
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(data);
          }
        } catch (error) {
          console.error('Error processing OpenAI message:', error);
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
        console.log('OpenAI WebSocket connection closed');
      });

    } catch (error) {
      console.error('Error initializing OpenAI connection:', error);
    }
  };

  // Handle messages from Exotel
  ws.on('message', (data) => {
    try {
      console.log('Received message from Exotel');
      
      // Initialize OpenAI connection if not already done
      if (!openaiWs || openaiWs.readyState !== WebSocket.OPEN) {
        initOpenAI();
        
        // Wait a moment for connection to establish
        setTimeout(() => {
          if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
            openaiWs.send(data);
          }
        }, 1000);
      } else {
        // Forward message to OpenAI
        openaiWs.send(data);
      }
    } catch (error) {
      console.error('Error handling Exotel message:', error);
    }
  });

  ws.on('close', () => {
    console.log('Exotel WebSocket connection closed');
    if (openaiWs) {
      openaiWs.close();
    }
  });

  ws.on('error', (error) => {
    console.error('Exotel WebSocket error:', error);
    if (openaiWs) {
      openaiWs.close();
    }
  });

  // Send welcome message
  ws.send(JSON.stringify({
    type: 'connection_established',
    message: 'Connected to Bakery Bot Server'
  }));
});

// Start server
server.listen(PORT, () => {
  console.log(`Bakery Bot WebSocket Server running on port ${PORT}`);
  console.log(`WebSocket URL: ws://localhost:${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Shutting down server...');
  wss.clients.forEach((ws) => {
    ws.close();
  });
  server.close(() => {
    console.log('Server stopped');
    process.exit(0);
  });
});
