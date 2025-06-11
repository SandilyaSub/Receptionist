const WebSocket = require('ws');
const readline = require('readline');

// Configuration
const WSS_URL = 'wss://receptionist-production.up.railway.app/';
const DEFAULT_MODE = 'text'; // 'text' or 'audio'

// State tracking
let sessionReady = false;
let currentMode = DEFAULT_MODE;
let assistantResponding = false;
let lastResponseText = '';

// Set up readline interface for interactive testing
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

console.log(`Attempting to connect to ${WSS_URL}`);

const ws = new WebSocket(WSS_URL);

ws.on('open', () => {
  console.log('Connected to WebSocket server.');
  console.log('Waiting for session to be configured...');
});

ws.on('message', (data) => {
  let message;
  try {
    message = JSON.parse(data);
    
    // Handle different message types
    switch (message.type) {
      case 'connection_established':
        console.log('Connection established with server:', message.message);
        break;
        
      case 'session.created':
        console.log('Session created with ID:', message.session.id);
        break;
        
      case 'session.updated':
        handleSessionUpdated(message);
        break;
        
      case 'message':
        handleBotMessage(message);
        break;
        
      case 'response.output_item.delta':
        handleResponseDelta(message);
        break;
        
      case 'response.output_item.done':
        handleResponseDone(message);
        break;
        
      case 'error':
        console.error('Error from server:', message.error || message.message);
        break;
        
      case 'mode_switched':
        console.log(`Mode switched to: ${message.mode}`);
        break;
        
      default:
        // For other message types, just log the type
        console.log(`Received message of type: ${message.type}`);
    }
  } catch (e) {
    // Handle binary data or non-JSON messages
    if (Buffer.isBuffer(data)) {
      console.log(`Received binary data of length: ${data.length} bytes`);
    } else {
      console.log('Received non-JSON message:', data.toString().substring(0, 100));
    }
  }
});

// Handle session update - this means we're ready to send messages
function handleSessionUpdated(message) {
  console.log('Session updated with modalities:', message.session.modalities);
  sessionReady = true;
  
  // Update our current mode based on the session
  currentMode = message.session.modalities.includes('audio') ? 'audio' : 'text';
  console.log(`Operating in ${currentMode} mode`);
  
  // Prompt the user for input
  promptForInput();
}

// Handle bot messages
function handleBotMessage(message) {
  if (message.role === 'assistant') {
    assistantResponding = true;
    console.log('\nAssistant is responding...');
  }
}

// Handle response deltas (incremental text responses)
function handleResponseDelta(message) {
  if (message.delta && message.delta.text) {
    process.stdout.write(message.delta.text);
    lastResponseText += message.delta.text;
  }
}

// Handle response completion
function handleResponseDone(message) {
  if (assistantResponding) {
    console.log('\n\nAssistant response complete.');
    assistantResponding = false;
    promptForInput();
  }
}

// Prompt the user for input
function promptForInput() {
  console.log('\nCommands:');
  console.log('  /mode text   - Switch to text-only mode');
  console.log('  /mode audio  - Switch to audio mode');
  console.log('  /exit        - Close the connection');
  console.log('  <text>       - Send a message to the bot');
  
  rl.question('> ', (input) => {
    if (input.trim().toLowerCase() === '/exit') {
      console.log('Closing connection...');
      ws.close();
      rl.close();
      return;
    }
    
    if (input.trim().toLowerCase() === '/mode text') {
      sendModeSwitch('text');
      return;
    }
    
    if (input.trim().toLowerCase() === '/mode audio') {
      sendModeSwitch('audio');
      return;
    }
    
    if (sessionReady) {
      sendUserMessage(input);
    } else {
      console.log('Session not ready yet. Please wait...');
      setTimeout(promptForInput, 1000);
    }
  });
}

// Send a mode switch request
function sendModeSwitch(mode) {
  console.log(`Requesting switch to ${mode} mode...`);
  ws.send(JSON.stringify({
    type: 'mode_switch',
    mode: mode
  }));
}

// Send a user message
function sendUserMessage(text) {
  const message = {
    type: 'message',
    role: 'user',
    status: 'in_progress',
    content: [
      {
        type: 'input_text',
        text: text
      }
    ]
  };
  
  console.log(`Sending message: ${JSON.stringify(message, null, 2)}`);
  ws.send(JSON.stringify(message));
  lastResponseText = '';
}

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', () => {
  console.log('WebSocket connection closed.');
  rl.close();
  process.exit(0);
});

// Handle process termination
process.on('SIGINT', () => {
  console.log('\nReceived SIGINT. Closing connection...');
  ws.close();
  rl.close();
  process.exit(0);
});
