#!/usr/bin/env python3
"""
Interactive Test Client for Exotel-Gemini Bridge
This client connects to the WebSocket server, captures audio from the microphone,
sends it to the server, and plays back audio responses.
"""

import asyncio
import base64
import json
import logging
import os
import sys
import threading
import time
import traceback
import wave
from typing import Optional

import pyaudio
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestMicrophoneClient")

# Audio settings
FORMAT = pyaudio.paInt16  # 16-bit audio
CHANNELS = 1  # Mono
RATE = 16000  # 16kHz (matching Gemini's expected input rate)
CHUNK = 1024  # Number of frames per buffer
RECORD_SECONDS = 5  # Default recording duration
SERVER_URL = "ws://localhost:8765"  # WebSocket server URL

# Global variables
recording = False
should_exit = False
pya = pyaudio.PyAudio()


class AudioClient:
    """Client for capturing audio from microphone and playing back responses."""
    
    def __init__(self):
        """Initialize the audio client."""
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.websocket = None
        self.recording = False
    
    def start_recording(self):
        """Start recording audio from the microphone."""
        if self.stream is not None:
            logger.warning("Recording is already active")
            return
        
        logger.info("Starting audio recording")
        self.recording = True
        self.stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    
    def stop_recording(self):
        """Stop recording audio from the microphone."""
        if self.stream is None:
            logger.warning("No active recording to stop")
            return
        
        logger.info("Stopping audio recording")
        self.recording = False
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
    
    def play_audio(self, audio_data: bytes):
        """Play audio data through the speakers."""
        try:
            # Log audio data details for debugging
            logger.debug(f"Audio data length: {len(audio_data)} bytes")
            logger.debug(f"Audio data first few bytes: {audio_data[:20]}")
            
            # Ensure audio data is not empty
            if len(audio_data) == 0:
                logger.warning("Received empty audio data, skipping playback")
                return
                
            # Normalize audio volume (optional - might help if audio is too quiet)
            # This is a simple approach to increase volume if needed
            try:
                # Convert bytes to numpy array for processing
                import numpy as np
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Check if audio has actual content (not just silence)
                max_amplitude = np.max(np.abs(audio_array))
                logger.debug(f"Max audio amplitude: {max_amplitude}")
                
                if max_amplitude > 0:
                    # Normalize to 50% of maximum possible amplitude
                    # This will make quiet audio louder
                    target_amplitude = 16384  # 50% of max int16 (32767)
                    if max_amplitude < target_amplitude:
                        gain_factor = target_amplitude / max_amplitude
                        audio_array = np.clip(audio_array * gain_factor, -32768, 32767).astype(np.int16)
                        logger.debug(f"Applied gain factor: {gain_factor}")
                        # Convert back to bytes
                        audio_data = audio_array.tobytes()
                        logger.debug("Audio volume normalized")
            except Exception as e:
                logger.warning(f"Audio normalization failed: {e}, continuing with original audio")
            
            # Open audio stream
            stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True
            )
            
            # Write audio data in chunks to avoid potential buffer issues
            chunk_size = 1024
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                stream.write(chunk)
            
            logger.debug("Audio playback completed")
            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()


async def send_audio(websocket, audio_client: AudioClient):
    """Capture audio from the microphone and send it to the server."""
    global recording, should_exit
    
    logger.info("Press 'r' to start/stop recording, 'q' to quit")
    
    while not should_exit:
        if recording and audio_client.stream is not None:
            try:
                # Read audio data from the microphone
                data = audio_client.stream.read(CHUNK, exception_on_overflow=False)
                
                # Send audio data to the server with sample rate information
                await websocket.send(json.dumps({
                    "event": "media",
                    "media": {
                        "payload": base64.b64encode(data).decode('utf-8')
                    },
                    "sample_rate": RATE  # Include the sample rate (16kHz)
                }))
                
                # Small delay to avoid flooding the server
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                break
        else:
            # If not recording, just wait a bit
            await asyncio.sleep(0.1)


async def receive_audio(websocket, audio_client: AudioClient):
    """Receive audio responses from the server and play them back."""
    global should_exit
    
    while not should_exit:
        try:
            # Receive message from the server
            message = await websocket.recv()
            data = json.loads(message)
            
            if data["event"] == "media":
                # Decode and play audio
                audio_data = base64.b64decode(data["media"]["payload"])
                logger.info("Received audio response, playing back...")
                
                # Save received audio for debugging
                debug_dir = "client_debug_audio"
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = int(time.time())
                raw_file = os.path.join(debug_dir, f"client_received_audio_{timestamp}.raw")
                with open(raw_file, "wb") as f:
                    f.write(audio_data)
                logger.info(f"Saved received audio to {raw_file}")
                
                # Also save as WAV for easy playback
                wav_file = os.path.join(debug_dir, f"client_received_audio_{timestamp}.wav")
                with wave.open(wav_file, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(audio_data)
                logger.info(f"Saved received audio as WAV to {wav_file}")
                
                # Play in a separate thread to avoid blocking
                threading.Thread(
                    target=audio_client.play_audio,
                    args=(audio_data,)
                ).start()
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
            break
        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            break


async def keyboard_input():
    """Handle keyboard input for controlling recording."""
    global recording, should_exit
    
    while not should_exit:
        key = await asyncio.to_thread(input, "Press 'r' to start/stop recording, 'q' to quit\n")
        key = key.lower()
        
        if key == 'r':
            recording = not recording
            print(f"Recording {'started' if recording else 'stopped'}")
            
            # Send end_of_speech event when stopping recording
            if not recording and current_websocket is not None:
                await send_end_of_speech()
        elif key == 'q':
            should_exit = True
            print("Exiting...")
            break


# Global websocket for the end_of_speech function
current_websocket: Optional[websockets.WebSocketClientProtocol] = None


async def send_end_of_speech():
    """Send end_of_speech event to the server."""
    global current_websocket
    
    if current_websocket is not None:
        try:
            logger.info("Sending end_of_speech event")
            await current_websocket.send(json.dumps({
                "event": "end_of_speech"
            }))
            logger.info("End_of_speech event sent successfully")
        except Exception as e:
            logger.error(f"Error sending end_of_speech: {e}")


async def main():
    """Main function to run the client."""
    global current_websocket, should_exit
    
    audio_client = AudioClient()
    
    try:
        logger.info(f"Connecting to {SERVER_URL}")
        async with websockets.connect(SERVER_URL) as websocket:
            current_websocket = websocket
            logger.info("Connected to the server")
            
            # Create tasks for sending and receiving audio, and handling keyboard input
            send_task = asyncio.create_task(send_audio(websocket, audio_client))
            receive_task = asyncio.create_task(receive_audio(websocket, audio_client))
            keyboard_task = asyncio.create_task(keyboard_input())
            
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                [send_task, receive_task, keyboard_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    except Exception as e:
        logger.error(f"Error: {e}")
        traceback_info = traceback.format_exc()
        logger.error(f"Traceback: {traceback_info}")
    
    finally:
        # Clean up resources
        audio_client.cleanup()
        should_exit = True
        logger.info("Client shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
