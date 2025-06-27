const WebSocket = require('ws');

// Configuration
const WSS_URL = 'wss://receptionist-production.up.railway.app/';
const TEST_MESSAGES = [
  'Hello, I would like to order a cake.',
  'Do you have chocolate cake?',
  'What size options do you have?',
  'I would like a medium chocolate cake for tomorrow.'
];

// Connect to the WebSocket server
console.log(`Connecting to ${WSS_URL}...`);
const ws = new WebSocket(WSS_URL);

let messageIndex = 0;
let sessionReady = false;

ws.on('open', () => {
  console.log('Connected to WebSocket server.');
  console.log('Waiting for session to be configured...');
});

ws.on('message', (data) => {
  let message;
  try {
    message = JSON.parse(data);
    
    // Log message type for debugging
    console.log(`Received message type: ${message.type}`);
    
    // Handle session update - this means we're ready to send messages
    if (message.type === 'session.updated') {
      console.log('Session configured with modalities:', message.session.modalities);
      sessionReady = true;
      
      // Send the first test message
      sendNextMessage();
    }
    
    // Handle response completion
    if (message.type === 'response.output_item.done') {
      console.log('\nAssistant response complete.');
      
      // Send the next message after a delay
      setTimeout(() => {
        sendNextMessage();
      }, 2000);
    }
    
    // Handle response deltas (incremental text responses)
    if (message.type === 'response.output_item.delta' && message.delta && message.delta.text) {
      process.stdout.write(message.delta.text);
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

// Send the next message in the test sequence
function sendNextMessage() {
  if (messageIndex < TEST_MESSAGES.length) {
    const text = TEST_MESSAGES[messageIndex];
    console.log(`\n\nSending test message ${messageIndex + 1}/${TEST_MESSAGES.length}: "${text}"`);
    
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
    
    ws.send(JSON.stringify(message));
    messageIndex++;
  } else {
    console.log('\n\nTest conversation complete. Closing connection.');
    ws.close();
    process.exit(0);
  }
}

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
  process.exit(1);
});

ws.on('close', () => {
  console.log('WebSocket connection closed.');
  process.exit(0);
});

// Handle process termination
process.on('SIGINT', () => {
  console.log('\nReceived SIGINT. Closing connection...');
  ws.close();
  process.exit(0);
});
