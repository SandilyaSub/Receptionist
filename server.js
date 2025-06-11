
// server.js (with enhanced logging)
const WebSocket = require('ws');
// const https = require('https'); // Not used if Railway handles SSL termination

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

  // **QUERY: Is this message below actually being sent by your server?**
  // If so, it should be here. Example:
  // ws.send(JSON.stringify({ type: "connection_established", message: "Connected to Bakery Bot Server from server.js" }));
  // console.log(`[${clientIp}] Sent initial connection established message.`);

  let openaiWs = null;

  const connectToOpenAI = () => {
    console.log(`[${clientIp}] Attempting to connect to OpenAI Realtime API...`);
    const url = 'wss://api.openai.com/v1/realtime?gpt-4o-realtime-preview-2025-06-03'; // Consider making model configurable

    openaiWs = new WebSocket(url, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'OpenAI-Beta': 'realtime=v1'
      }
    });

    openaiWs.on('open', () => {
      console.log(`[${clientIp}] Successfully connected to OpenAI Realtime API.`);
      // const sessionConfig = { /* ... your sessionConfig ... */ }; // Defined globally now
      try {
        openaiWs.send(JSON.stringify(sessionConfig));
        console.log(`[${clientIp}] Sent session configuration to OpenAI.`);
      } catch (e) {
        console.error(`[${clientIp}] ERROR sending session config to OpenAI:`, e);
      }
    });

    openaiWs.on('message', (data) => {
      console.log(`[${clientIp}] Received message from OpenAI. Type: ${typeof data}, Length: ${data.length || 'N/A'}`);
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(data);
          // console.log(`[${clientIp}] Forwarded OpenAI message to client.`); // Can be very verbose
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
    console.log(`[${clientIp}] Received message from Client (Exotel). Type: ${typeof message}, IsBuffer: ${Buffer.isBuffer(message)}, Length: ${message.length || 'N/A'}`);
    // If it's text and short, log it. If binary, avoid logging full content unless small.
    if (!Buffer.isBuffer(message) && message.length < 200) {
        console.log(`[${clientIp}] Client message content (text): ${message.toString()}`);
    } else if (Buffer.isBuffer(message)) {
        console.log(`[${clientIp}] Client message content (binary buffer of length ${message.length}). First few bytes (hex): ${message.slice(0, 16).toString('hex')}`);
    }


    if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
      try {
        openaiWs.send(message); // Forward raw message (Buffer or string)
        // console.log(`[${clientIp}] Forwarded client message to OpenAI.`); // Can be verbose
      } catch (error) {
        console.error(`[${clientIp}] ERROR forwarding client message to OpenAI:`, error);
      }
    } else {
      console.warn(`[${clientIp}] OpenAI WebSocket not open or not initialized when client message received. openaiWs readyState: ${openaiWs ? openaiWs.readyState : 'null'}`);
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`[${clientIp}] Client (Exotel) disconnected. Code: ${code}, Reason: ${reason ? reason.toString() : 'N/A'}`);
    if (openaiWs) {
      console.log(`[${clientIp}] Closing OpenAI WebSocket due to client disconnection.`);
      openaiWs.close();
    }
  });

  ws.on('error', (error) => {
    console.error(`[${clientIp}] Client (Exotel) WebSocket error:`, error.message, error.code || '');
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

