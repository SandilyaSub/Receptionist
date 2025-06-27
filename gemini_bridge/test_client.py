#!/usr/bin/env python3
"""
Test client for the Gemini Bridge WebSocket server

This client connects to the Gemini Bridge WebSocket server, sends audio data,
and receives audio responses from Gemini.
"""

import asyncio
import json
import os
import wave
import argparse
import logging
from datetime import datetime

import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_client")

# Default server URL
DEFAULT_SERVER_URL = "ws://localhost:8082"

async def send_audio_file(websocket, audio_file_path):
    """Send an audio file to the server"""
    try:
        with wave.open(audio_file_path, 'rb') as wav_file:
            # Get audio file properties
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            logger.info(f"Audio file: {audio_file_path}")
            logger.info(f"  Channels: {channels}")
            logger.info(f"  Sample width: {sample_width} bytes")
            logger.info(f"  Frame rate: {frame_rate} Hz")
            logger.info(f"  Number of frames: {n_frames}")
            
            # Read all audio data
            audio_data = wav_file.readframes(n_frames)
            
            # Send audio data in chunks
            chunk_size = 1024  # 1KB chunks
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                await websocket.send(chunk)
                logger.info(f"Sent audio chunk: {len(chunk)} bytes")
                await asyncio.sleep(0.05)  # Small delay to simulate real-time streaming
            
            # Signal end of audio
            await websocket.send(json.dumps({
                "type": "user_audio_end"
            }))
            logger.info("Sent end-of-audio signal")
            
    except Exception as e:
        logger.error(f"Error sending audio file: {str(e)}")
        raise

async def save_audio_response(audio_data, output_dir):
    """Save audio data to a WAV file"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"gemini_response_{timestamp}.pcm")
    
    with open(output_file, 'wb') as f:
        f.write(audio_data)
    
    logger.info(f"Saved audio response to {output_file}")
    return output_file

async def main(server_url, audio_file_path, output_dir):
    """Main function to run the test client"""
    logger.info(f"Connecting to server at {server_url}")
    
    try:
        async with websockets.connect(server_url) as websocket:
            logger.info("Connected to server")
            
            # Create a queue for received messages
            message_queue = asyncio.Queue()
            
            # Start the receiver task
            receiver_task = asyncio.create_task(message_receiver(websocket, message_queue))
            
            # Wait for initial connection message
            initial_msg_received = False
            while not initial_msg_received:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=5.0)
                    if isinstance(message, str):
                        try:
                            data = json.loads(message)
                            if data.get("type") == "connection_established":
                                initial_msg_received = True
                                logger.info("Received connection confirmation")
                        except json.JSONDecodeError:
                            pass
                    message_queue.task_done()
                except asyncio.TimeoutError:
                    logger.error("Timed out waiting for connection confirmation")
                    return
            
            # Start the processor task
            processor_task = asyncio.create_task(message_processor(message_queue, output_dir))
            
            # Send audio file
            logger.info(f"Sending audio file: {audio_file_path}")
            await send_audio_file(websocket, audio_file_path)
            
            # Wait for a while to receive responses
            await asyncio.sleep(10)  # Wait for 10 seconds to receive responses
            
            # Cancel tasks
            receiver_task.cancel()
            processor_task.cancel()
            
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass
                
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"Error: {str(e)}")

async def message_receiver(websocket, message_queue):
    """Receive messages from the WebSocket and put them in the queue"""
    try:
        while True:
            message = await websocket.recv()
            await message_queue.put(message)
            if isinstance(message, bytes):
                logger.info(f"Received binary data: {len(message)} bytes")
            else:
                logger.info(f"Received text message")
    except asyncio.CancelledError:
        logger.info("Message receiver task cancelled")
    except Exception as e:
        logger.error(f"Error in message receiver: {str(e)}")

async def message_processor(message_queue, output_dir):
    """Process messages from the queue"""
    audio_buffer = bytearray()
    collecting_audio = False
    
    try:
        while True:
            message = await message_queue.get()
            
            if isinstance(message, bytes):
                # Binary message (audio data)
                logger.info(f"Processing audio chunk: {len(message)} bytes")
                audio_buffer.extend(message)
                collecting_audio = True
                
            elif isinstance(message, str):
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "unknown")
                    logger.info(f"Processing message type: {msg_type}")
                    
                    if msg_type == "transcription" and "text" in data:
                        logger.info(f"Transcription: {data['text']}")
                        
                    elif msg_type == "response.output_item.done":
                        if collecting_audio and audio_buffer:
                            # Save the collected audio
                            await save_audio_response(audio_buffer, output_dir)
                            audio_buffer = bytearray()
                            collecting_audio = False
                            
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON text message: {message}")
            
            message_queue.task_done()
                    
    except asyncio.CancelledError:
        logger.info("Message processor task cancelled")
        if collecting_audio and audio_buffer:
            # Save any collected audio before exiting
            await save_audio_response(audio_buffer, output_dir)
    except Exception as e:
        logger.error(f"Error in message processor: {str(e)}")
        if collecting_audio and audio_buffer:
            # Save any collected audio before exiting
            await save_audio_response(audio_buffer, output_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test client for Gemini Bridge")
    parser.add_argument("--server", type=str, default=DEFAULT_SERVER_URL,
                        help=f"WebSocket server URL (default: {DEFAULT_SERVER_URL})")
    parser.add_argument("--audio", type=str, required=True,
                        help="Path to audio file (WAV format)")
    parser.add_argument("--output", type=str, default="./responses",
                        help="Directory to save audio responses (default: ./responses)")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.server, args.audio, args.output))
