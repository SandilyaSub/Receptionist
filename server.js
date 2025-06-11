// server.js (with enhanced logging)
const WebSocket = require('ws');
const { URL } = require('url');

const PORT = process.env.PORT || 8080;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

if (!OPENAI_API_KEY) {
  console.error('ERROR: OPENAI_API_KEY environment variable is required');
  process.exit(1);
}

console.log('Starting Bakery Bot WebSocket Server (Enhanced Logging)...');

const wss = new WebSocket.Server({
  port: PORT,
  host: '0.0.0.0'
});

console.log(`Bakery Bot WebSocket Server running on port ${PORT}`);
console.log('Server is ready to accept connections');

// Define sessionConfig globally or pass it appropriately
const sessionConfig = {
    type: 'session.update',
    session: {
      modalities: ['text', 'audio'],
      instructions: 'You are a helpful bakery assistant. Help customers with their orders and questions about baked goods.',
      voice: 'alloy',
      input_audio_format: 'pcm16', // Crucial: Does Exotel send this?
      output_audio_format: 'pcm16',
      input_audio_transcription: {
        model: 'whisper-1'
      }
    }
  };

wss.on('connection', (ws, req) => {
  const clientIp = req.socket.remoteAddress || req.headers['x-forwarded-for'] || 'Unknown IP';
  console.log(`[${clientIp}] New client connected.`);
  console.log(`[${clientIp}] Request Headers: ${JSON.stringify(req.headers, null, 2)}`);

  // Send a welcome message to the client
  ws.send(JSON.stringify({ type: "connection_established", message: "Connected to Bakery Bot Server" }));
  console.log(`[${clientIp}] Sent initial connection established message.`);

  let openaiWs = null;
  const messageQueue = []; // Queue for messages that arrive before OpenAI is ready

  const connectToOpenAI = () => {
    console.log(`[${clientIp}] Attempting to connect to OpenAI Realtime API...`);
    // FIX: Correcting model date to 2024 and logging the final URL.
    const url = new URL('wss://api.openai.com/v1/realtime');
    url.searchParams.append('model', 'gpt-4o-realtime-preview-2024-06-03');
    console.log(`[${clientIp}] Connecting to OpenAI with URL: ${url.href}`);
    openaiWs = new WebSocket(url.href, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'OpenAI-Beta': 'realtime=v1'
      }
    });

    openaiWs.on('open', () => {
      console.log(`[${clientIp}] Successfully connected to OpenAI Realtime API.`);
      openaiWs.send(JSON.stringify(sessionConfig));
      console.log(`[${clientIp}] Sent session configuration to OpenAI.`);

      // FIX: Process any queued messages now that the connection is open
      console.log(`[${clientIp}] Processing ${messageQueue.length} queued messages.`);
      while (messageQueue.length > 0) {
        const queuedMessage = messageQueue.shift();
        openaiWs.send(queuedMessage);
        console.log(`[${clientIp}] Sent queued message to OpenAI.`);
      }
    });

    openaiWs.on('message', (data) => {
      // console.log(`[${clientIp}] Received message from OpenAI...`);
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(data);
        } catch (e) {
          console.error(`[${clientIp}] ERROR forwarding OpenAI message to client:`, e);
        }
      }
    });

    openaiWs.on('error', (error) => {
      console.error(`[${clientIp}] OpenAI WebSocket error:`, error.message, error.code || '');
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'error', message: 'OpenAI connection error: ' + error.message }));
        } catch (e) {
          console.error(`[${clientIp}] ERROR sending OpenAI error to client:`, e);
        }
      }
    });

    openaiWs.on('close', (code, reason) => {
      console.log(`[${clientIp}] OpenAI WebSocket closed. Code: ${code}, Reason: ${reason ? reason.toString() : 'N/A'}`);
    });
  };

  connectToOpenAI(); // Connect to OpenAI when Exotel connects

  ws.on('message', (message) => {
    const messageType = typeof message;
    const isBuffer = Buffer.isBuffer(message);
    const messageLength = isBuffer ? message.length : (message.length || 'N/A');

    console.log(`[${clientIp}] Received message from Client. Type: ${messageType}, IsBuffer: ${isBuffer}, Length: ${messageLength}`);
    
    // FIX: Queue messages if OpenAI connection is not ready, otherwise send directly.
    if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
      openaiWs.send(message);
      console.log(`[${clientIp}] Forwarded message to OpenAI.`);
    } else {
      console.log(`[${clientIp}] OpenAI WebSocket not ready. Queuing message.`);
      messageQueue.push(message);
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`[${clientIp}] Client disconnected. Code: ${code}, Reason: ${reason ? reason.toString() : 'N/A'}`);
    if (openaiWs) {
      console.log(`[${clientIp}] Closing OpenAI connection due to client disconnect.`);
      openaiWs.close();
    }
  });

  ws.on('error', (error) => {
    console.error(`[${clientIp}] Client WebSocket error:`, error);
    if (openaiWs) {
      console.log(`[${clientIp}] Closing OpenAI connection due to client error.`);
      openaiWs.close();
    }
  });
});

wss.on('error', (error) => {
  console.error('WebSocket Server Global Error:', error.message, error.code || '');
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down gracefully');
  wss.close();
});

process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down gracefully');
  wss.close();
});

