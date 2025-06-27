#!/usr/bin/env python3
"""
Gemini Bridge - WebSocket server that bridges a browser client to Google's Gemini LiveAPI

This server accepts WebSocket connections, forwards audio from the client to Gemini's
LiveAPI (using client.aio.live.connect), and streams Gemini's audio responses back to the client.
It follows the pattern from the official Gemini cookbook for LiveAPI usage.
"""

import asyncio
import logging
import os
import traceback
import wave
import io
import json # For sending structured messages like ack/error

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import traceback # For logging exceptions
import uvicorn # For running the FastAPI app
import google.genai as genai
from google.genai import types, errors
import numpy as np

# --- Configuration ---
load_dotenv() # Load .env file for local development

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Model compatible with the Live API, from the official Gemini Cookbook.
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "models/gemini-2.0-flash-live-001")

# System prompt (shortened for debugging)
SYSTEM_PROMPT = "You are a helpful and friendly bakery receptionist."

# Gemini Client Initialization
# Create a single client instance, specifying the v1beta API version as used in the cookbook.
gemini_client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1beta"})

# Audio parameters
INPUT_SAMPLE_RATE = 16000  # Client (browser) sends audio at this rate (PCM s16le)
AUDIO_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2 # 16-bit PCM

# --- FastAPI App Initialization ---
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws/gemini_bridge")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_ip = websocket.client.host
    session_id = str(uuid.uuid4())
    logger.info(f"WebSocket connection accepted from {client_ip} (Session ID: {session_id})")
    audio_filename = f"temp_audio_{session_id}.wav"

    try:
        await websocket.send_json({"type": "connection_ack", "message": "Connection established. Please send audio file."})

        # Wait for the client to send the audio file as a single bytes message.
        audio_bytes = await websocket.receive_bytes()
        logger.info(f"[{session_id}] Received {len(audio_bytes)} bytes of audio data.")

        # Save the received bytes as a temporary WAV file.
        with wave.open(audio_filename, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000) # 16kHz
            wf.writeframes(audio_bytes)

        # Upload the audio file to Gemini.
        logger.info(f"[{session_id}] Uploading {audio_filename} to Gemini...")
        audio_file = gemini_client.upload_file(path=audio_filename)
        logger.info(f"[{session_id}] Completed upload: {audio_file.uri}")

        # Get the response from the model.
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        logger.info(f"[{session_id}] Sending audio to Gemini for analysis...")
        response = model.generate_content(["What is in this audio?", audio_file])

        # Send the response back to the client.
        logger.info(f"[{session_id}] Received response from Gemini: {response.text}")
        await websocket.send_json({"type": "bot_text", "data": response.text})

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"[{session_id}] An unexpected error occurred: {e}")
        logger.error(traceback.format_exc())
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass # Client might already be disconnected
    finally:
        # Clean up the audio file from the server and the uploaded file from Gemini.
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
            logger.info(f"[{session_id}] Deleted temporary file: {audio_filename}")
        # The 'audio_file' object might not exist if an error occurred before it was created.
        if 'audio_file' in locals() and audio_file:
            try:
                logger.info(f"[{session_id}] Deleting uploaded file from Gemini: {audio_file.name}")
                gemini_client.delete_file(name=audio_file.name)
            except Exception as e:
                logger.error(f"[{session_id}] Error deleting Gemini file {audio_file.name}: {e}")
        logger.info(f"[{session_id}] Closing WebSocket connection for {client_ip}.")


if __name__ == "__main__":
    logger.info("Starting Gemini Bridge server (non-streaming) on port 8080")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
