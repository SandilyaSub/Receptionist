# Gemini Bridge

A WebSocket server that bridges between Exotel telephony and Google's Gemini LiveAPI for voice bot integration.

## Overview

This project creates a bridge server that:
1. Accepts WebSocket connections from Exotel
2. Connects to Google's Gemini LiveAPI
3. Forwards audio from Exotel to Gemini
4. Returns Gemini's audio responses back to Exotel

## Features

- Real-time audio streaming between Exotel and Gemini
- Support for PCM audio format
- Detailed logging for debugging
- Simple health check endpoint
- Test client for local verification

## Requirements

- Python 3.9+
- Google Gemini API key
- Exotel account (for production use)

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file from the template:
   ```
   cp .env.example .env
   ```
4. Add your Gemini API key to the `.env` file

## Usage

### Starting the server

```
python gemini_bridge.py
```

The server will start on port 8080 by default. You can change this by setting the `PORT` environment variable.

### Testing with the test client

1. Prepare a WAV audio file (PCM format, 16-bit, 16kHz, mono recommended)
2. Run the test client:
   ```
   python test_client.py --audio path/to/your/audio.wav
   ```
3. The client will connect to the server, send the audio, and save any responses to the `./responses` directory

## Deployment

### Railway.app

This server is designed to be deployed on Railway.app:

1. Push the code to GitHub
2. Connect your GitHub repository to Railway
3. Set the `GEMINI_API_KEY` environment variable in Railway
4. Deploy the application

### Exotel Integration

To integrate with Exotel:

1. Deploy the bridge server to Railway or another cloud provider
2. Configure Exotel to connect to your deployed WebSocket server URL
3. Ensure the audio format matches between Exotel and Gemini

## License

MIT
