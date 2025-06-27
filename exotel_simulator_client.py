#!/usr/bin/env python3
"""
Exotel Simulator Client
A WebSocket client that simulates Exotel's behavior for testing the Exotel-Gemini Bridge.
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
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExotelSimulator")

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000  # Exotel uses 8kHz audio
CHUNK_SIZE = int(RATE / 10)  # 100ms chunks (same as Exotel example)

# Debug audio saving disabled for performance

class ExotelSimulatorClient:
    """Simulates an Exotel client connecting to our Exotel-Gemini Bridge."""
    
    def __init__(self, server_url: str):
        """Initialize the Exotel simulator client.
        
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
        
    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to {self.server_url}")
        self.websocket = await websockets.connect(self.server_url)
        logger.info("Connected to server")
        
        # Send connected message
        await self.send_message({
            "event": "connected",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid
        })
        
        # Send start message with call information
        await self.send_message({
            "event": "start",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid,
            "start": {
                "stream_sid": self.stream_sid,
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "from": "+1234567890",  # Simulated caller number
                "to": "+9876543210",    # Simulated recipient number
                "custom_parameters": {
                    "client": "simulator",
                    "test": "true"
                },
                "media_format": {
                    "encoding": "LINEAR16",
                    "bit_rate": "128000"
                }
            }
        })
        
    async def send_message(self, message):
        """Send a message to the server.
        
        Args:
            message: Message to send
        """
        if self.websocket:
            message_json = json.dumps(message)
            await self.websocket.send(message_json)
            logger.debug(f"Sent message: {message['event']}")
        else:
            logger.warning("Cannot send message: not connected")
    
    def next_sequence_number(self):
        """Get the next sequence number for messages."""
        self.sequence_number += 1
        return self.sequence_number
    
    async def start_recording(self):
        """Start recording audio from the microphone."""
        if self.recording:
            logger.warning("Already recording")
            return
        
        logger.info("Starting audio recording")
        self.recording = True
        
        # Open microphone stream
        try:
            self.input_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            logger.info("Microphone stream opened")
        except Exception as e:
            logger.error(f"Error opening microphone: {e}")
            self.recording = False
            return
        
        # Start recording in a separate task
        asyncio.create_task(self.record_audio())
    
    async def stop_recording(self):
        """Stop recording audio."""
        if not self.recording:
            logger.warning("Not recording")
            return
        
        logger.info("Stopping audio recording")
        self.recording = False
        
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
    
    async def record_audio(self):
        """Record audio from the microphone and send to the server."""
        logger.info("Recording audio...")
        
        while self.recording and self.websocket and not self.websocket.closed:
            try:
                # Read audio data from microphone
                audio_data = self.input_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Debug audio saving disabled for performance
                
                # Encode as base64 and send to server
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                await self.send_message({
                    "event": "media",
                    "sequence_number": self.next_sequence_number(),
                    "stream_sid": self.stream_sid,
                    "media": {
                        "payload": audio_base64
                    }
                })
                
                # Simulate real-time by waiting a bit
                await asyncio.sleep(0.1)  # 100ms chunks
                
            except Exception as e:
                logger.error(f"Error recording audio: {e}")
                if not self.recording:
                    break
        
        logger.info("Audio recording stopped")
    
    async def send_dtmf(self, digit):
        """Send a DTMF digit to the server.
        
        Args:
            digit: DTMF digit to send (0-9, *, #)
        """
        await self.send_message({
            "event": "dtmf",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid,
            "dtmf": {
                "digit": digit
            }
        })
        logger.info(f"Sent DTMF digit: {digit}")
    
    async def send_mark(self, name="mark"):
        """Send a mark message to the server.
        
        Args:
            name: Name of the mark
        """
        await self.send_message({
            "event": "mark",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid,
            "mark": {
                "name": name
            }
        })
        logger.info(f"Sent mark: {name}")
    
    async def send_clear(self):
        """Send a clear message to the server."""
        await self.send_message({
            "event": "clear",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid,
            "clear": {}
        })
        logger.info("Sent clear message")
    
    async def send_stop(self, reason="user_requested"):
        """Send a stop message to the server.
        
        Args:
            reason: Reason for stopping
        """
        await self.send_message({
            "event": "stop",
            "sequence_number": self.next_sequence_number(),
            "stream_sid": self.stream_sid,
            "stop": {
                "call_sid": self.call_sid,
                "account_sid": self.account_sid,
                "reason": reason
            }
        })
        logger.info(f"Sent stop message: {reason}")
    
    async def receive_messages(self):
        """Receive and process messages from the server."""
        if not self.websocket:
            logger.error("Cannot receive messages: not connected")
            return
        
        # Open output stream for audio playback
        self.output_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True
        )
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"Received message: {data['event'] if 'event' in data else 'unknown'}")
                    
                    if "event" in data:
                        if data["event"] == "media":
                            # Process audio data
                            audio_base64 = data["media"]["payload"]
                            audio_data = base64.b64decode(audio_base64)
                            
                            # Debug audio saving disabled for performance
                            logger.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
                            
                            # Play audio
                            logger.info(f"Playing audio chunk of size: {len(audio_data)} bytes")
                            self.output_stream.write(audio_data)
                        
                        elif data["event"] == "mark":
                            # Mark message received
                            if "mark" in data and "name" in data["mark"]:
                                name = data["mark"]["name"]
                                logger.info(f"Received mark: {name}")
                
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
        finally:
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
    
    async def close(self):
        """Close the connection to the server."""
        logger.info("Closing connection")
        
        if self.recording:
            await self.stop_recording()
        
        if self.websocket and not self.websocket.closed:
            await self.send_stop()
            await self.websocket.close()
            self.websocket = None
        
        if self.audio:
            self.audio.terminate()
        
        logger.info("Connection closed")

async def interactive_client(server_url):
    """Run an interactive Exotel simulator client.
    
    Args:
        server_url: WebSocket server URL to connect to
    """
    client = ExotelSimulatorClient(server_url)
    
    try:
        # Connect to the server
        await client.connect()
        
        # Start receiving messages in a separate task
        receive_task = asyncio.create_task(client.receive_messages())
        
        # Display instructions
        print("\nExotel Simulator Client")
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
        await client.close()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Exotel Simulator Client')
    parser.add_argument('--host', type=str, default='localhost', help='Server hostname')
    parser.add_argument('--port', type=int, default=8765, help='Server port')
    parser.add_argument('--path', type=str, default='/media', help='WebSocket endpoint path')
    args = parser.parse_args()
    
    server_url = f"ws://{args.host}:{args.port}{args.path}"
    
    try:
        asyncio.run(interactive_client(server_url))
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()
