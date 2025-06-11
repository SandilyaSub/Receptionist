const WebSocket = require('ws');
const fs = require('fs');
const wav = require('wav');

// --- Configuration ---
const WSS_URL = 'wss://receptionist-production.up.railway.app/';
const INPUT_AUDIO_FILE = 'test_audio.wav';
const OUTPUT_AUDIO_FILE = 'response.wav';
const CHUNK_SIZE = 1024 * 4; // Size of audio chunks to send

// --- State ---
let sessionReady = false;
let modeSwitched = false;
let responseAudioBuffers = [];

// --- Main Logic ---
console.log(`Attempting to connect to ${WSS_URL}`);
const ws = new WebSocket(WSS_URL);

ws.on('open', () => {
  console.log('Connected to WebSocket server.');
  console.log('Waiting for session to be configured...');
});

ws.on('message', (data) => {
  try {
    // Attempt to parse as JSON first.
    const message = JSON.parse(data);
    console.log(`Received JSON message from server: ${message.type}`);

    switch (message.type) {
      case 'session.updated':
        if (!sessionReady) { // Process only once
            console.log('Session is ready. Requesting to switch to audio mode...');
            sessionReady = true;
            // We only send the mode switch request here.
            // We will start streaming audio only AFTER the server confirms the switch.
            sendModeSwitch('audio');
        }
        break;
      case 'mode_switched':
        if (message.mode === 'audio' && !modeSwitched) { // Process only once
          console.log('Mode switched to audio by server. NOW starting to stream audio file...');
          modeSwitched = true;
          streamAudioFile(); // Audio streaming starts only after server confirmation.
        } else if (message.mode === 'audio' && modeSwitched) {
          // Potentially a duplicate message, or a re-confirmation. Safe to ignore if already switched.
          console.log('Already in audio mode. Ignoring redundant mode_switched message.');
        } else if (message.mode !== 'audio'){
          console.warn(`Server switched to unexpected mode: ${message.mode}`);
        }
        break;
      case 'response.output_item.done': // This is a JSON message from OpenAI
        console.log('Bot has finished responding (JSON signal).');
        setTimeout(saveResponseAudio, 500);
        break;
      case 'error':
        console.error('Received error from server (JSON):', message.error || message.message);
        break;
      default:
        // console.log(`Received unhandled JSON message type: ${message.type}`);
    }
  } catch (e) {
    // If JSON parsing fails, it might be an audio buffer (or a malformed JSON string)
    if (Buffer.isBuffer(data)) {
      if (modeSwitched) { // Only treat as audio if we are in audio mode and expecting it
        console.log(`Received audio data chunk of size: ${data.length}`);
        responseAudioBuffers.push(data);
      } else {
        console.log(`Received unexpected audio buffer (size: ${data.length}) before audio mode fully active. Ignoring.`);
      }
    } else {
      // It's not a buffer and not valid JSON
      console.warn('Received non-JSON, non-buffer message:', data.toString());
    }
  }
});

function sendModeSwitch(mode) {
  ws.send(JSON.stringify({ type: 'mode_switch', mode: mode }));
}

function streamAudioFile() {
  if (!fs.existsSync(INPUT_AUDIO_FILE)) {
    console.error(`\nERROR: Input audio file not found at '${INPUT_AUDIO_FILE}'`);
    console.error('Please provide a test audio file in PCM 16-bit, 8000Hz, mono format.');
    ws.close();
    return;
  }

  const fileReader = new wav.Reader();
  fileReader.on('format', (format) => {
    console.log('Input WAV file format:', format);
    if (format.sampleRate !== 8000 || format.channels !== 1 || format.bitDepth !== 16) {
      console.error(`\nERROR: Unsupported audio format. Please use PCM 16-bit, 8000Hz, mono.`);
      ws.close();
    }
  });

  fileReader.on('data', (chunk) => {
    ws.send(chunk);
    console.log(`Sent audio chunk of size: ${chunk.length}`);
  });

  fileReader.on('end', () => {
    console.log('Finished sending audio file.');
    // Signal the end of user audio input
    ws.send(JSON.stringify({ type: 'user_audio_end' }));
  });

  const fileStream = fs.createReadStream(INPUT_AUDIO_FILE);
  fileStream.pipe(fileReader);
}

function saveResponseAudio() {
  if (responseAudioBuffers.length === 0) {
    console.log('No audio received from the bot.');
    ws.close();
    return;
  }

  console.log(`Saving received audio to ${OUTPUT_AUDIO_FILE}...`);
  const totalLength = responseAudioBuffers.reduce((acc, buffer) => acc + buffer.length, 0);
  const concatenatedBuffer = Buffer.concat(responseAudioBuffers, totalLength);

  const writer = new wav.Writer({
    channels: 1,
    sampleRate: 8000,
    bitDepth: 16
  });

  const fileStream = fs.createWriteStream(OUTPUT_AUDIO_FILE);
  writer.pipe(fileStream);
  writer.end(concatenatedBuffer);

  fileStream.on('finish', () => {
    console.log('Successfully saved response audio.');
    ws.close();
  });
}

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', (code, reason) => {
  console.log(`WebSocket connection closed. Code: ${code}, Reason: ${reason}`);
  if (responseAudioBuffers.length > 0) {
    saveResponseAudio(); // Attempt to save any partial audio we received
  }
});
