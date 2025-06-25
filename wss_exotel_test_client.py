#!/usr/bin/env python3
"""
WSS Exotel Test Client
A WebSocket client that simulates Exotel's behavior for testing the deployed Exotel-Gemini Bridge.
"""

import os
import asyncio
import base64
import json
import logging
import time
import uuid
import argparse
import pyaudio
import websockets
import ssl
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WSSExotelTester")

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000  # Exotel uses 8kHz audio
CHUNK_SIZE = int(RATE / 10)  # 100ms chunks (same as Exotel example)

class WSSExotelTestClient:
    """Simulates an Exotel client connecting to our deployed WSS Exotel-Gemini Bridge."""
    
    def __init__(self, server_url: str):
        """Initialize the WSS Exotel test client.
        
        Args:
            server_url: WebSocket server URL to connect to
        """
        self.server_url = server_url
        self.websocket = None
        self.stream_sid = str(uuid.uuid4())
        self.call_sid = str(uuid.uuid4())
        self.account_sid = "AC" + str(uuid.uuid4()).replace("-", "")
        self.sequence_number = 0
        self.recording = False
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.is_shutting_down = False  # Flag to track shutdown state
        
    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to {self.server_url}")
        
        try:
            # Determine if we need SSL based on the URL scheme
            if self.server_url.startswith("wss://"):
                # Create SSL context for WSS connections
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                self.websocket = await websockets.connect(
                    self.server_url,
                    ssl=ssl_context
                )
            else:
                # No SSL for ws:// connections
                self.websocket = await websockets.connect(self.server_url)
                
            logger.info("Connected to server")
            
            # Initialize audio streams
            self.input_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            self.output_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Send the start message
            await self.send_start()
            
            # Send the connected message
            await self.send_connected()
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        # Set the shutdown flag first to prevent further audio processing
        self.is_shutting_down = True
        logger.info("Starting client shutdown")
        
        if self.recording:
            await self.stop_recording()
            
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
            
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
            
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        if self.audio:
            self.audio.terminate()
            
        logger.info("Disconnected from server")
    
    async def send_start(self):
        """Send a start message to the server."""
        # Extract tenant from the server URL
        tenant = "bakery"  # Default tenant
        url_parts = self.server_url.split('/')
        for part in url_parts:
            if part in ["bakery", "saloon", "media"]:
                tenant = part
                break
        
        logger.info(f"Including tenant '{tenant}' in start message")
        
        message = {
            "event": "start",
            "start": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "tenant": tenant  # Include tenant ID in the start message
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"Sent start message with tenant '{tenant}'")
    
    async def send_connected(self):
        """Send a connected message to the server."""
        # Extract tenant from the server URL
        tenant = "bakery"  # Default tenant
        url_parts = self.server_url.split('/')
        for part in url_parts:
            if part in ["bakery", "saloon", "media"]:
                tenant = part
                break
        
        logger.info(f"Including tenant '{tenant}' in connected message")
        
        message = {
            "event": "connected",
            "connected": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "tenant": tenant  # Include tenant ID in the connected message
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"Sent connected message with tenant '{tenant}'")
    
    async def send_stop(self):
        """Send a stop message to the server."""
        message = {
            "event": "stop",
            "stop": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info("Sent stop message")
    
    async def send_mark(self):
        """Send a mark message to the server."""
        message = {
            "event": "mark",
            "mark": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info("Sent mark message")
    
    async def send_clear(self):
        """Send a clear message to the server."""
        message = {
            "event": "clear",
            "clear": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info("Sent clear message")
    
    async def send_dtmf(self, digit: str):
        """Send a DTMF digit to the server.
        
        Args:
            digit: DTMF digit to send (0-9, *, #)
        """
        message = {
            "event": "dtmf",
            "dtmf": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "digit": digit
            },
            "sequence_number": self.sequence_number
        }
        self.sequence_number += 1
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"Sent DTMF digit: {digit}")
    
    async def start_recording(self):
        """Start recording audio and sending it to the server."""
        if self.recording:
            logger.warning("Already recording")
            return
        
        self.recording = True
        logger.info("Started recording")
        
        try:
            while self.recording:
                # Read audio data from the microphone
                audio_data = self.input_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Encode the audio data as base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Send the audio data to the server
                message = {
                    "event": "media",
                    "media": {
                        "stream_sid": self.stream_sid,
                        "call_sid": self.call_sid,
                        "account_sid": self.account_sid,
                        "payload": audio_base64,
                        "timestamp": int(time.time() * 1000),  # Current time in milliseconds
                        "sample_rate": RATE,
                        "channels": CHANNELS
                    },
                    "sequence_number": self.sequence_number
                }
                self.sequence_number += 1
                
                await self.websocket.send(json.dumps(message))
                
                # Sleep for a short time to simulate real-time audio
                await asyncio.sleep(0.1)  # 100ms chunks
                
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            self.recording = False
    
    async def stop_recording(self):
        """Stop recording audio."""
        if not self.recording:
            logger.warning("Not recording")
            return
        
        self.recording = False
        logger.info("Stopped recording")
    
    async def receive_messages(self):
        """Receive and process messages from the server."""
        try:
            while True:
                # Receive a message from the server
                message = await self.websocket.recv()
                
                try:
                    # Parse the message as JSON
                    data = json.loads(message)
                    event = data.get("event")
                    
                    if event == "media":
                        # Extract the audio data
                        media = data.get("media", {})
                        payload = media.get("payload")
                        
                        if payload:
                            # Decode the base64 audio data
                            audio_data = base64.b64decode(payload)
                            
                            # Play the audio data only if not shutting down and output stream exists
                            if not self.is_shutting_down and self.output_stream:
                                self.output_stream.write(audio_data)
                            else:
                                logger.debug("Skipping audio playback during shutdown")
                        
                        logger.debug("Received media message")
                    else:
                        logger.info(f"Received message: {message}")
                
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message: {message}")
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed")
        
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")

async def interactive_client(server_url):
    """Run an interactive WSS Exotel test client.
    
    Args:
        server_url: WebSocket server URL to connect to
    """
    client = WSSExotelTestClient(server_url)
    
    try:
        # Connect to the server
        await client.connect()
        
        # Start receiving messages in a separate task
        receive_task = asyncio.create_task(client.receive_messages())
        
        # Display instructions
        print("\nWSS Exotel Test Client")
        print("======================")
        print("Commands:")
        print("  r - Start/stop recording")
        print("  1-9, 0, *, # - Send DTMF digit")
        print("  m - Send mark")
        print("  c - Send clear")
        print("  s - Send stop")
        print("  q - Quit")
        print("======================\n")
        
        # Process user commands
        while True:
            command = await asyncio.to_thread(input, "> ")
            
            if command.lower() == 'q':
                break
            elif command.lower() == 'r':
                if client.recording:
                    await client.stop_recording()
                else:
                    await client.start_recording()
            elif command in "0123456789*#":
                await client.send_dtmf(command)
            elif command.lower() == 'm':
                await client.send_mark()
            elif command.lower() == 'c':
                await client.send_clear()
            elif command.lower() == 's':
                await client.send_stop()
            else:
                print(f"Unknown command: {command}")
        
        # Cancel the receive task
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
    
    finally:
        # Close the connection
        await client.disconnect()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WSS Exotel Test Client")
    parser.add_argument(
        "--environment",
        choices=["local", "railway"],
        default="railway",
        help="Environment to connect to (local or railway)"
    )
    parser.add_argument(
        "--server", 
        default=None,
        help="Custom WebSocket server URL (overrides --environment if provided)"
    )
    parser.add_argument(
        "--tenant",
        choices=["bakery", "saloon", "media"],
        default="bakery",
        help="Tenant to connect to (bakery, saloon, or media for backward compatibility)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number for local server (only used when --environment=local)"
    )
    args = parser.parse_args()
    
    # Determine the base server URL based on environment
    if args.server:
        # Custom server URL provided, use it directly
        base_url = args.server
    elif args.environment == "local":
        # Local environment
        base_url = f"ws://0.0.0.0:{args.port}"
    else:
        # Railway environment (default)
        base_url = "wss://receptionist-production.up.railway.app"
    
    # Construct the full URL with tenant path
    full_url = f"{base_url}/{args.tenant}"
    print(f"Connecting to tenant: {args.tenant} at URL: {full_url}")
    
    # Run the interactive client
    try:
        asyncio.run(interactive_client(full_url))
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()
