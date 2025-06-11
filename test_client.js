const WebSocket = require('ws');

// Replace with your Railway WSS URL
const WSS_URL = 'wss://receptionist-production.up.railway.app/';

console.log(`Attempting to connect to ${WSS_URL}`)

const ws = new WebSocket(WSS_URL);

ws.on('open', () => {
  console.log('Connected to WebSocket server.');

  // Send a test message (text for now)
  // Your server.js currently forwards raw messages. OpenAI expects JSON for session config,
  // but for text interaction after session config, it might accept raw text or specific JSON.
  // Let's start with a simple text message. If this doesn't work, we might need to send JSON.
  const testMessage = "Hello Bakery, I would like to ask about your cakes.";
  console.log(`Sending message: "${testMessage}"`);
  ws.send(testMessage);
});

ws.on('message', (data) => {
  console.log('Received message from server:');
  // Try to parse as JSON if it looks like it, otherwise print as string
  try {
    const jsonData = JSON.parse(data.toString());
    console.log(JSON.stringify(jsonData, null, 2));
  } catch (e) {
    console.log(data.toString());
  }
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error.message);
});

ws.on('close', (code, reason) => {
  console.log(`WebSocket connection closed. Code: ${code}, Reason: ${reason ? reason.toString() : 'No reason given'}`);
});

// To keep the client running for a bit to receive messages, otherwise it might exit immediately.
// You can manually close it with Ctrl+C after testing.
// setTimeout(() => {
//   if (ws.readyState === WebSocket.OPEN) {
//     console.log('Closing client after timeout.');
//     ws.close();
//   }
// }, 30000); // Keep alive for 30 seconds
