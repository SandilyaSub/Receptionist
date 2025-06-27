#!/usr/bin/env python3
"""
Local Exotel Test Client
A WebSocket client that simulates Exotel's behavior for testing the local Exotel-Gemini Bridge.
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
logger = logging.getLogger("LocalExotelTester")

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000  # Exotel uses 8kHz audio
CHUNK_SIZE = int(RATE / 10)  # 100ms chunks (same as Exotel example)

class LocalExotelTestClient:
    """Simulates an Exotel client connecting to our local Exotel-Gemini Bridge."""
    
    def __init__(self, server_url: str):
        """Initialize the local Exotel test client.
        
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
        
        # Extract tenant from URL if present
        self.tenant = "bakery"  # Default tenant
        if "/" in server_url.split("://")[-1]:
            parts = server_url.split("/")
            if len(parts) > 3:  # Has a path component
                self.tenant = parts[-1]
        
        logger.info(f"Using tenant: {self.tenant}")
    
    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to {self.server_url}")
        
        try:
            # For local testing, we don't need SSL verification
            self.websocket = await websockets.connect(
                self.server_url,
                ssl=None,
                ping_interval=None,  # Disable automatic pings
                close_timeout=10     # Longer timeout for closing
            )
            
            logger.info("Connected to server")
            
            # Initialize audio output stream
            self.output_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Send start message
            await self.send_start_message()
            
            # Wait a moment for the server to process the start message
            await asyncio.sleep(1)
            
            # Send connected message
            await self.send_connected_message()
            
            # Wait another moment for the server to process the connected message
            await asyncio.sleep(1)
            
            logger.info("Initialization sequence completed")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
        
        # Audio output stream is initialized in the connect method
    
    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        logger.info("Starting client shutdown")
        
        # Stop recording if active
        if self.recording:
            await self.stop_recording()
        
        # Close audio streams
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        # Close audio
        self.audio.terminate()
        
        # Close WebSocket connection
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")
    
    async def send_message(self, message):
        """Send a message to the server.
        
        Args:
            message: The message to send
        """
        if self.websocket and not self.is_shutting_down:
            await self.websocket.send(json.dumps(message))
            self.sequence_number += 1
    
    async def send_start_message(self):
        """Send the start message to initiate the session."""
        start_message = {
            "start": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "from": "+1234567890",
                "to": "+0987654321",
                "custom_parameters": {
                    "tenant": self.tenant
                }
            }
        }
        
        logger.info(f"Sent start message with tenant '{self.tenant}'")
        await self.send_message(start_message)
    
    async def send_connected_message(self):
        """Send the connected message."""
        connected_message = {
            "connected": {
                "stream_sid": self.stream_sid,
                "custom_parameters": {
                    "tenant": self.tenant
                }
            }
        }
        
        logger.info(f"Including tenant '{self.tenant}' in connected message")
        await self.send_message(connected_message)
    
    async def send_mark(self):
        """Send a mark message."""
        mark_message = {
            "mark": {
                "name": "test_mark"
            }
        }
        await self.send_message(mark_message)
        logger.info("Sent mark message")
    
    async def send_dtmf(self, digit):
        """Send a DTMF digit.
        
        Args:
            digit: The DTMF digit to send (0-9, *, #)
        """
        dtmf_message = {
            "dtmf": {
                "digit": digit
            }
        }
        await self.send_message(dtmf_message)
        logger.info(f"Sent DTMF digit: {digit}")
    
    async def send_clear(self):
        """Send a clear message."""
        clear_message = {
            "clear": {}
        }
        await self.send_message(clear_message)
        logger.info("Sent clear message")
    
    async def send_stop(self):
        """Send a stop message."""
        stop_message = {
            "stop": {}
        }
        await self.send_message(stop_message)
        logger.info("Sent stop message")
    
    async def start_recording(self):
        """Start recording audio from the microphone."""
        if self.recording:
            logger.info("Already recording")
            return
        
        # Make sure we have a valid session before starting to record
        if not self.stream_sid or not self.call_sid:
            logger.error("Cannot start recording: No active session (missing stream_sid or call_sid)")
            return
            
        # Initialize the input stream
        self.input_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        self.recording = True
        logger.info("Started recording")
        
        # Start the recording task
        asyncio.create_task(self._record_audio())
    
    async def stop_recording(self):
        """Stop recording audio."""
        if not self.recording:
            logger.info("Not recording")
            return
        
        self.recording = False
        logger.info("Stopped recording")
    
    async def _record_audio(self):
        """Record audio from the microphone and send it to the server."""
        try:
            while self.recording and not self.is_shutting_down:
                # Read audio data from the microphone
                data = self.input_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Encode the audio data as base64
                encoded_data = base64.b64encode(data).decode('utf-8')
                
                # Send the audio data to the server
                media_message = {
                    "media": {
                        "track": "inbound",
                        "chunk": encoded_data,
                        "timestamp": int(time.time() * 1000)
                    }
                }
                await self.send_message(media_message)
                
                # Sleep briefly to avoid flooding the server
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Error in recording task: {e}")
            self.recording = False
    
    async def receive_messages(self):
        """Receive and process messages from the server."""
        try:
            while not self.is_shutting_down:
                try:
                    # Receive a message from the server with timeout
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                    logger.info(f"Received message: {message}")
                    
                    # Parse the message
                    try:
                        data = json.loads(message)
                        
                        # Handle media messages (audio playback)
                        if "media" in data and self.output_stream:
                            media = data["media"]
                            if "chunk" in media:
                                # Decode the base64 audio data
                                audio_data = base64.b64decode(media["chunk"])
                                
                                # Play the audio
                                self.output_stream.write(audio_data)
                        
                        # Handle mark messages (could contain session info)
                        if "mark" in data:
                            mark_name = data.get("mark", {}).get("name", "")
                            if "session_ready" in mark_name:
                                logger.info("Server indicates session is ready")
                                
                        # Log any error messages from server
                        if "error" in data:
                            logger.error(f"Server error: {data['error']}")
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON: {message}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
                except asyncio.TimeoutError:
                    logger.warning("No message received for 30 seconds, sending ping")
                    try:
                        # Send a ping to keep the connection alive
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=5)
                        logger.debug("Received pong from server")
                    except Exception as e:
                        logger.error(f"Ping failed: {e}")
                        break
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed by server: {e.code} - {e.reason}")
        except Exception as e:
            logger.error(f"Error in receive task: {e}")
        finally:
            # Ensure we disconnect properly
            if not self.is_shutting_down:
                await self.disconnect()

async def interactive_client(server_url):
    """Run an interactive local Exotel test client.
    
    Args:
        server_url: WebSocket server URL to connect to
    """
    # Create and connect the client
    client = LocalExotelTestClient(server_url)
    connected = await client.connect()
    
    if not connected:
        logger.error("Failed to establish connection. Exiting.")
        return
    
    # Wait for server to initialize the session
    logger.info("Waiting for server to initialize session...")
    await asyncio.sleep(2)
        
    # Start the receive task
    receive_task = asyncio.create_task(client.receive_messages())
    
    try:
        print("\nLocal Exotel Test Client")
        print("======================")
        print("Commands:")
        print("  r - Start/stop recording")
        print("  1-9, 0, *, # - Send DTMF digit")
        print("  m - Send mark")
        print("  c - Send clear")
        print("  s - Send stop")
        print("  q - Quit")
        print("======================\n")
        
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
    parser = argparse.ArgumentParser(description="Local Exotel Test Client")
    parser.add_argument(
        "--host", 
        default="localhost",
        help="Host to connect to (default: localhost)"
    )
    parser.add_argument(
        "--port", 
        default="8765",
        help="Port to connect to (default: 8765)"
    )
    parser.add_argument(
        "--tenant",
        choices=["bakery", "saloon", "media"],
        default="bakery",
        help="Tenant to connect to (bakery, saloon, or media)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger("LocalExotelTester").setLevel(logging.DEBUG)
        print("Debug logging enabled")
    
    # Construct the full URL with tenant path
    full_url = f"ws://{args.host}:{args.port}/{args.tenant}"
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
