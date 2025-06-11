const WebSocket = require('ws');

// Replace with your Railway WSS URL
const WSS_URL = 'wss://receptionist-production.up.railway.app/';

console.log(`Attempting to connect to ${WSS_URL}`)

const ws = new WebSocket(WSS_URL);

ws.on('open', () => {
  console.log('Connected to WebSocket server.');
  // We will now wait for the session to be confirmed before sending a message.
});

ws.on('message', (data) => {
  console.log('Received message from server:');
  let message;
  try {
    message = JSON.parse(data);
    console.log(JSON.stringify(message, null, 2));
  } catch (e) {
    console.log('Received non-JSON message:', data);
    return;
  }

  // FIX: Wait for the session to be fully configured before sending our prompt.
  if (message.type === 'session.updated') {
    console.log('Session is updated and ready. Sending text input...');
    const testMessage = {
      type: 'text.input',
      text: 'Hello Bakery, I would like to ask about your cakes.'
    };
    console.log(`Sending message: ${JSON.stringify(testMessage, null, 2)}`);
    ws.send(JSON.stringify(testMessage));
  }
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', () => {
  console.log('WebSocket connection closed.');
});
//     console.log('Closing client after timeout.');
//     ws.close();
//   }
// }, 30000); // Keep alive for 30 seconds
