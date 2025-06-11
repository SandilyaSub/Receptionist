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

// Define session configurations based on modality
const textSessionConfig = {
  type: 'session.update',
  session: {
    modalities: ['text'],
    instructions: 'You are a helpful bakery assistant. Help customers with their orders and questions about baked goods.',
    voice: 'alloy' // Keep voice parameter as it's required by the API
  }
};

// Audio session config for when we integrate with Exotel
const audioSessionConfig = {
  type: 'session.update',
  session: {
    modalities: ['text', 'audio'],
    instructions: 'You are a helpful bakery assistant. Help customers with their orders and questions about baked goods.',
    voice: 'alloy',
    input_audio_format: 'pcm16', // Update this to match Exotel's format when known
    output_audio_format: 'pcm16',
    turn_detection: { type: 'server_vad' },
    input_audio_transcription: { model: 'whisper-1' }
  }
};

// Track all active connections
const connections = new Map();

wss.on('connection', (ws, req) => {
  const clientIp = req.socket.remoteAddress || req.headers['x-forwarded-for'] || 'Unknown IP';
  console.log(`[${clientIp}] New client connected.`);
  console.log(`[${clientIp}] Request Headers: ${JSON.stringify(req.headers, null, 2)}`);

  // Create a unique connection ID
  const connectionId = Date.now().toString();
  
  // Initialize connection state
  const connectionState = {
    clientWs: ws,
    openaiWs: null,
    messageQueue: [],
    isAudioMode: false, // Default to text mode for now
    clientIp
  };
  
  connections.set(connectionId, connectionState);

  // Send a welcome message to the client
  ws.send(JSON.stringify({ type: "connection_established", message: "Connected to Bakery Bot Server" }));
  console.log(`[${clientIp}] Sent initial connection established message.`);

  const connectToOpenAI = () => {
    console.log(`[${clientIp}] Attempting to connect to OpenAI Realtime API...`);
    
    // Use the model as a query parameter in the URL as seen in the Twilio demo
    const url = new URL('wss://api.openai.com/v1/realtime');
    url.searchParams.append('model', 'gpt-4o-realtime-preview');
    console.log(`[${clientIp}] Connecting to OpenAI with URL: ${url.href}`);
    
    const openaiWs = new WebSocket(url.href, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'OpenAI-Beta': 'realtime=v1' // Important header from Twilio demo
      }
    });
    
    connectionState.openaiWs = openaiWs;

    openaiWs.on('open', () => {
      console.log(`[${clientIp}] Successfully connected to OpenAI Realtime API.`);
      
      // Use the appropriate session config based on mode
      const sessionConfig = connectionState.isAudioMode ? audioSessionConfig : textSessionConfig;
      openaiWs.send(JSON.stringify(sessionConfig));
      console.log(`[${clientIp}] Sent ${connectionState.isAudioMode ? 'audio' : 'text'} session configuration to OpenAI.`);

      // Process any queued messages now that the connection is open
      console.log(`[${clientIp}] Processing ${connectionState.messageQueue.length} queued messages.`);
      while (connectionState.messageQueue.length > 0) {
        const queuedMessage = connectionState.messageQueue.shift();
        openaiWs.send(queuedMessage);
        console.log(`[${clientIp}] Sent queued message to OpenAI.`);
      }
    });

    openaiWs.on('message', (data) => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          // Log important message types for debugging
          try {
            const parsedData = JSON.parse(data.toString());
            console.log(`[${clientIp}] Received message from OpenAI: ${parsedData.type || 'unknown type'}`);
          } catch (e) {
            // If it's not JSON (like audio buffer), don't log the content
            console.log(`[${clientIp}] Received binary data from OpenAI`);
          }
          
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

  connectToOpenAI(); // Connect to OpenAI when client connects

  ws.on('message', (message) => {
    const clientIp = connectionState.clientIp;

    // 1. Handle Audio Buffers
    if (Buffer.isBuffer(message)) {
      if (connectionState.isAudioMode) {
        if (connectionState.openaiWs && connectionState.openaiWs.readyState === WebSocket.OPEN) {
          connectionState.openaiWs.send(message);
        } else {
          console.log(`[${clientIp}] Audio received but OpenAI WS not ready. Discarding.`);
        }
      } else {
        console.log(`[${clientIp}] Received audio buffer in text-only mode. Ignoring.`);
      }
      return; // End of handling for this message
    }

    // 2. Handle JSON Control Messages
    try {
      const parsedMessage = JSON.parse(message);
      console.log(`[${clientIp}] Received JSON message. Type: ${parsedMessage.type}`);

      if (parsedMessage.type === 'mode_switch' && parsedMessage.mode) {
        // Handle mode switch
        connectionState.isAudioMode = parsedMessage.mode === 'audio';
        console.log(`[${clientIp}] Switching to ${connectionState.isAudioMode ? 'audio' : 'text'} mode.`);
        if (connectionState.openaiWs && connectionState.openaiWs.readyState === WebSocket.OPEN) {
          const sessionConfig = connectionState.isAudioMode ? audioSessionConfig : textSessionConfig;
          connectionState.openaiWs.send(JSON.stringify(sessionConfig));
          console.log(`[${clientIp}] Sent session update for ${parsedMessage.mode} mode.`);
        }
        ws.send(JSON.stringify({ type: 'mode_switched', mode: parsedMessage.mode }));

      } else if (parsedMessage.type === 'user_audio_end') {
        // Handle end of user audio
        console.log(`[${clientIp}] Client signaled end of audio stream.`);
        if (connectionState.openaiWs && connectionState.openaiWs.readyState === WebSocket.OPEN) {
          const endMessage = { type: 'message', role: 'user', status: 'done' };
          connectionState.openaiWs.send(JSON.stringify(endMessage));
          console.log(`[${clientIp}] Sent user 'done' message to OpenAI.`);
        }

      } else {
        // Forward other JSON messages (e.g., text input)
        if (connectionState.openaiWs && connectionState.openaiWs.readyState === WebSocket.OPEN) {
          console.log(`[${clientIp}] Forwarding message to OpenAI:`, JSON.stringify(parsedMessage));
          connectionState.openaiWs.send(JSON.stringify(parsedMessage));
        } else {
          console.log(`[${clientIp}] OpenAI WS not ready. Queuing message.`);
          connectionState.messageQueue.push(JSON.stringify(parsedMessage));
        }
      }
    } catch (e) {
      console.error(`[${clientIp}] Failed to parse incoming message as JSON. Error: ${e.message}. Message: ${message.toString()}`);
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`[${clientIp}] Client disconnected. Code: ${code}, Reason: ${reason ? reason.toString() : 'N/A'}`);
    
    // Clean up OpenAI connection
    if (connectionState.openaiWs) {
      console.log(`[${clientIp}] Closing OpenAI connection due to client disconnect.`);
      connectionState.openaiWs.close();
      connectionState.openaiWs = null;
    }
    
    // Remove from connections map
    connections.delete(connectionId);
    console.log(`[${clientIp}] Connection removed. Active connections: ${connections.size}`);
  });

  ws.on('error', (error) => {
    console.error(`[${clientIp}] Client WebSocket error:`, error);
    
    // Clean up OpenAI connection
    if (connectionState.openaiWs) {
      console.log(`[${clientIp}] Closing OpenAI connection due to client error.`);
      connectionState.openaiWs.close();
      connectionState.openaiWs = null;
    }
    
    // Remove from connections map
    connections.delete(connectionId);
    console.log(`[${clientIp}] Connection removed due to error. Active connections: ${connections.size}`);
  });
});

wss.on('error', (error) => {
  console.error('WebSocket Server Global Error:', error.message, error.code || '');
});

// Function to clean up all connections
function cleanupAllConnections() {
  console.log(`Cleaning up all connections. Active count: ${connections.size}`);
  
  for (const [id, connection] of connections.entries()) {
    if (connection.openaiWs) {
      connection.openaiWs.close();
    }
    if (connection.clientWs) {
      connection.clientWs.close();
    }
    connections.delete(id);
  }
  
  console.log('All connections cleaned up.');
}

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down gracefully');
  cleanupAllConnections();
  wss.close();
});

process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down gracefully');
  cleanupAllConnections();
  wss.close();
});

// Log active connections periodically
setInterval(() => {
  console.log(`Active connections: ${connections.size}`);
}, 60000); // Log every minute
