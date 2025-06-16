#!/usr/bin/env python3
"""
Exotel-Gemini Bridge
A WebSocket server that bridges audio between Exotel and the Gemini Live API.
Built based on patterns from Gemini_Live_actual.py and Exotel's streaming example.
"""

import os
import asyncio
import base64
import json
import logging
import audioop
import uuid
import time
import warnings
from typing import Dict, Optional

import websockets
from google import genai
from google.genai import types

# Configure logging to both console and file
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# Create a file handler that logs to a new file each run
log_file = os.path.join(log_dir, f"exotel_bridge_{int(time.time())}.log")

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Suppress specific warnings from the google-genai library
logging.getLogger('google.genai.text').setLevel(logging.ERROR)

# Filter out specific warnings about non-text parts in the response
warnings.filterwarnings("ignore", message="there are non-text parts in the response")
warnings.filterwarnings("ignore", message=".*inline_data.*")

# Note: genai.configure() is not available in this version of the library
# Using warnings.filterwarnings() instead

# Constants
EXOTEL_SAMPLE_RATE = 8000  # Exotel uses 8kHz audio (16-bit, mono PCM little-endian)
GEMINI_SAMPLE_RATE = 16000  # Gemini expects 16kHz audio input
GEMINI_OUTPUT_SAMPLE_RATE = 24000  # Default Gemini output sample rate (will be used if detection fails)
# Note: We'll try to detect Gemini's output sample rate, but fall back to this default if needed

# Default port (will be overridden by PORT environment variable in Railway)
DEFAULT_PORT = 8765

# Load API key from environment variable
# SECURITY NOTE: Always use environment variables in production
# Try to load from environment variable first
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Load from .env file if available (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            logging.info("Loaded API key from .env file")
except ImportError:
    pass

# Check if API key is available
if not GEMINI_API_KEY:
    logging.error("GEMINI_API_KEY environment variable not set")
    raise ValueError("GEMINI_API_KEY environment variable must be set")

# Initialize Gemini client
client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=GEMINI_API_KEY,
)

# Gemini configuration based on Gemini_Live_actual.py
GEMINI_CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    system_instruction=types.Content(
        parts=[types.Part.from_text(text="""You are working as a receptionist at this bakery taking user orders. 
Be courteous and respond properly. Do this in an Indian accent.

Towards the start of the conversation, ask the customer for his name, so that you can use that to address him during the conversation.

At the end of the conversation, the expectation is that you would have figured out all the relevant details that a baker needs to make a cake and keep it ready. You will tell the customer the price that would be incurred and a timeslot by when the cake would be ready, so that he could pick it up. The menu is towards the bottom of the instructions. The time a customer can come and pick the cake up would be 6hrs for making the cake and the cake is made only during the working hours. 

Typical preferences that customers would need to hear from you are - 
- flavour of the cake,
- egg / eggless, 
- add-ons that are required like chocolates / some sprinkles, 
- size of the cake in KGs, 
- shape of the cake & occasion
- what is to be written on the cake or any further customizations.

DONOT ANSWER ANY IRRELEVANT QUESTIONS THAT ARE BEYOND THE SCOPE MENTIONED HERE. IF A CUSTOMERS ASKS SUCH A QUESTION POLITELY REPLY THAT YOU ARE SORRY AND CAN'T ANSWER THAT QUESTION AT THIS TIME. 

If a difficult question for which you are unsure of what the answer could be is asked, just reply to the customer that someone from the store will call you back during the next available working hour slot. 
---------------------------
Menu
Open Hours: 10am - 9pm

A-La-Carte Desserts
Russian Medovik – RS 160.00

Opera – RS 180.00

Belgian Truffle – RS 180.00

German Chocolate Cakeslice – RS 140.00

Tres Leches – RS 160.00

Baked Cheese Cake Slice – RS 160.00

Cupcakes
Coconut Crumble – RS 80.00

Chocolate Cheese Cake – RS 80.00

Coffee Caramel – RS 80.00

Classic Red Velvet – RS 80.00

Dairy Milk – RS 80.00

Blueberry – RS 80.00

Decadent Chocolate – RS 80.00

Macarons
Elachi Toffee – RS 60.00

Mewa Rabri – RS 60.00

Coconut – RS 60.00

Lemon Curd – RS 60.00

Banoffee – RS 60.00

Dark Chocolate – RS 60.00

Raspberry – RS 60.00

Dessert Tubs
Tiramisu – RS 280.00

Biscoff – RS 280.00

Chocolate Mousse – RS 280.00

Banoffee – RS 280.00

Bakery & Confectionery
English Toffee – RS 180.00

Caramel Popcorn – RS 180.00

Nan Khataai – RS 300.00

Chocolate Chip Cookies – RS 300.00

Almond Biscotti – RS 300.00

Oatmeal Cookies – RS 300.00

Chocolates
Couverture Chocolate (Each RS 60.00):

Sugarfree Fudge (Dates, Cashew & Sugarfree Dark)

Sugarfree Fruit n Nut (Dried Raspberry, Roasted Almond & Apricot)

Almond Rocks (Dark 45%, Roasted Almond)

Deep Brown (Dark Chocolate 70% Cocoa, Cocoa Nibs)

Banana Toffee (White Chocolate, White Banofee Ganache & Praline)

Kopra (White Chocolate, White Ganache Filling with Aged Coconut)

Salted Caramel (Milk Chocolate, Salted Caramel)

Raspberry Bombs (Milk Chocolate & Dried Raspberry Bits)

Mewa Rabri (Milk Chocolate, Mewa Rabri Filling)

Classic Dairy Milk (Milk Chocolate, Milk Ganache)

Hazelnut Praline (Milk Chocolate, Hazelnuts & Praline)

By the Box:

55% Cocoa Dark (Box of 12) – RS 700.00

55% Cocoa Dark (Box of 16) – RS 750.00

70% Cocoa Dark Sugarfree (Box of 12) – RS 650.00

70% Cocoa Dark Sugarfree (Box of 16) – RS 850.00

46.5% Cocoa Dry Fruit Collection (Box of 12) – RS 900.00

46.5% Cocoa Dry Fruit Collection (Box of 16) – RS 800.00

Cakes
(All cakes available in Half Kg / 1 Kg sizes)

Cake Name	Half Kg	1 Kg
(v) Dutch Truffle	RS 700	RS 1100
(v) Fruit Premium	RS 700	RS 1100
(v) Pineapple	RS 600	RS 900
(v) Dark Forest	RS 650	RS 950
(v) Butterscotch	RS 650	RS 950
(v) German Chocolate Cake	RS 700	RS 1100
(v) Ferroro Rocher Cake	RS 800	RS 1300
(v) Irish Coffee	RS 650	RS 950
Carrotcake	RS 650	RS 950
Blueberry Cheesecake (Cold Set)	RS 800	RS 1300
Tiramisu	RS 800	RS 1300
New York Cheesecake	RS 800	RS 1300
Choice of Topping (for Cheesecakes):

Plain – 0

Strawberry – 95

Caramel – 95

Blueberry – 95

Lemon Curd – 95

Raspberry – 95

Notes:

GST: 5% Extra

Cakes marked with (v) can be made eggless with an additional charge of RS 30 for 500 grams and RS 60 for 1 kg.

Products marked as eggless are also free from gelatin.""")],
        role="user"
    ),
)

# Audio processing helper functions
def resample_audio(audio_data: bytes, src_sample_rate: int, dst_sample_rate: int) -> bytes:
    """Resample audio data from source sample rate to destination sample rate.
    
    Args:
        audio_data: Audio data as bytes (16-bit PCM)
        src_sample_rate: Source sample rate in Hz
        dst_sample_rate: Destination sample rate in Hz
        
    Returns:
        Resampled audio data as bytes
    """
    # Skip resampling if rates are the same
    if src_sample_rate == dst_sample_rate:
        return audio_data
        
    # Ensure we have valid sample rates to avoid division by zero
    if src_sample_rate <= 0 or dst_sample_rate <= 0:
        logging.warning(f"Invalid sample rates: src={src_sample_rate}, dst={dst_sample_rate}. Using original audio.")
        return audio_data
    
    try:
        # Use audioop for resampling
        return audioop.ratecv(
            audio_data,
            2,  # 2 bytes per sample (16-bit)
            1,  # 1 channel (mono)
            src_sample_rate,
            dst_sample_rate,
            None
        )[0]
    except Exception as e:
        logging.error(f"Error during audio resampling: {e}")
        return audio_data  # Return original audio if resampling fails

class GeminiSession:
    """Manages a single Gemini session for a WebSocket connection."""
    
    def __init__(self, session_id: str, websocket):
        """
        Args:
            session_id: Unique identifier for this session
            websocket: WebSocket connection to communicate with the client
        """
        self.session_id = session_id
        self.websocket = websocket
        self.gemini_session = None
        self.logger = logging.getLogger(f"GeminiSession-{session_id}")
        
        # Exotel specific information
        self.stream_sid = None
        self.call_sid = None
        self.account_sid = None
        self.from_number = None
        self.to_number = None
        self.custom_parameters = {}
        self.sequence_number = 0
        
        # Audio buffer for combining chunks before sending to client
        self.audio_buffer = bytearray()
        self.buffer_threshold = 24000  # Buffer about 1 second of audio at 24kHz (smaller for more frequent sends)
        self.last_buffer_send_time = time.time()  # Track when we last sent audio
        self.buffer_time_threshold = 0.5  # Send buffer if it's been this many seconds since last send
        self.audio_chunk_counter = 0  # Counter for audio chunks (used for debugging)
        
        # Will be detected from first audio chunk
        self.gemini_output_sample_rate = None
    
    async def initialize(self):
        """Initialize the Gemini session."""
        self.logger.info("Initializing Gemini session")
        # Use async with to properly handle the AsyncGeneratorContextManager
        self.gemini_session = client.aio.live.connect(
            model="models/gemini-2.5-flash-preview-native-audio-dialog",
            config=GEMINI_CONFIG
        )
        self.logger.info("Gemini session initialized successfully")
    
    async def run(self):
        """Run the Gemini session, handling bidirectional audio streaming."""
        try:
            await self.initialize()
            
            # Use async with to properly handle the Gemini session
            async with self.gemini_session as session:
                self.gemini_session = session
                self.logger.info("Gemini session connected")
                
                # Create tasks for bidirectional streaming
                async with asyncio.TaskGroup() as tg:
                    # Task 1: Receive audio from Exotel and send to Gemini
                    tg.create_task(self.receive_from_exotel())
                    
                    # Task 2: Receive responses from Gemini and send to Exotel
                    tg.create_task(self.receive_from_gemini())
                
        except Exception as e:
            self.logger.error(f"Error in Gemini session: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def receive_from_exotel(self):
        """Receive audio from Exotel via WebSocket and send to Gemini."""
        self.logger.info("Starting to receive audio from Exotel")
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.logger.debug(f"Received message from Exotel: {data['event'] if 'event' in data else 'unknown event'}")
                    
                    if "event" in data:
                        # Handle Exotel protocol messages
                        if data["event"] == "connected":
                            self.logger.info("Connected message received from Exotel")
                            # No specific action needed for connected event
                            
                        elif data["event"] == "start":
                            self.logger.info("Start message received from Exotel")
                            # Extract and store session information
                            if "start" in data:
                                start_data = data["start"]
                                self.stream_sid = start_data.get("stream_sid")
                                self.call_sid = start_data.get("call_sid")
                                self.account_sid = start_data.get("account_sid")
                                self.from_number = start_data.get("from")
                                self.to_number = start_data.get("to")
                                self.custom_parameters = start_data.get("custom_parameters", {})
                                
                                self.logger.info(f"Stream started: stream_sid={self.stream_sid}, call_sid={self.call_sid}")
                            
                        elif data["event"] == "media":
                            # Process audio and send to Gemini
                            # Decode the base64 audio data
                            audio_data = base64.b64decode(data["media"]["payload"])
                            
                            # For Exotel, always use 8kHz as the source rate
                            client_sample_rate = EXOTEL_SAMPLE_RATE
                            
                            # Resample audio from Exotel's 8kHz to Gemini's 16kHz
                            self.logger.debug(f"Resampling audio from {client_sample_rate}Hz to {GEMINI_SAMPLE_RATE}Hz")
                            resampled_audio = resample_audio(audio_data, client_sample_rate, GEMINI_SAMPLE_RATE)
                            
                            # Send audio to Gemini
                            self.logger.debug("Sending audio chunk to Gemini")
                            await self.gemini_session.send_realtime_input(audio=types.Blob(
                                data=resampled_audio,
                                mime_type="audio/pcm"
                            ))
                        
                        elif data["event"] == "dtmf":
                            # Handle DTMF (touch-tone) input if needed
                            if "dtmf" in data and "digit" in data["dtmf"]:
                                digit = data["dtmf"]["digit"]
                                self.logger.info(f"DTMF digit received: {digit}")
                                # Could send this to Gemini as text if needed
                                await self.gemini_session.send_client_content(
                                    turns={"parts": [{"text": f"User pressed {digit}"}]},
                                    turn_complete=False
                                )
                        
                        elif data["event"] == "stop":
                            # Call is ending
                            self.logger.info("Stop message received from Exotel")
                            if "stop" in data and "reason" in data["stop"]:
                                reason = data["stop"]["reason"]
                                self.logger.info(f"Stream stopped: reason={reason}")
                            
                            # Signal turn completion to Gemini
                            await self.gemini_session.send_client_content(
                                turns={"parts": [{"text": ""}]}, 
                                turn_complete=True
                            )
                            # We'll exit the loop naturally when the websocket closes
                            
                        elif data["event"] == "mark":
                            # Mark event for tracking media completion
                            self.logger.info("Mark message received from Exotel")
                            # No specific action needed for mark event
                            
                        elif data["event"] == "clear":
                            # Clear event to stop playing queued audio
                            self.logger.info("Clear message received from Exotel")
                            # We could potentially clear our audio buffer here if needed
                            self.audio_buffer.clear()
                            self.last_buffer_send_time = time.time()
                except json.JSONDecodeError:
                    self.logger.warning("Received non-JSON message")
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
        
        except Exception as e:
            self.logger.error(f"Error in receive_from_exotel: {e}")
            raise
    
    async def receive_from_gemini(self):
        """Receive audio responses from Gemini and send to Exotel via WebSocket."""
        self.logger.info("Starting to receive responses from Gemini")
        
        try:
            # Use the same pattern as Gemini_Live_actual.py for receiving responses
            while True:
                turn = self.gemini_session.receive()
                self.logger.debug("Waiting for Gemini response turn")
                
                try:
                    async for response in turn:
                        self.logger.debug(f"Received response from Gemini: {response}")
                        
                        # Extract audio data from response
                        audio_data = None
                        
                        # Check for data in response.data first
                        if data := response.data:
                            audio_data = data
                            self.logger.debug("Found audio in response.data")
                        
                        # Check for inline_data if response.data is None
                        elif hasattr(response, 'parts') and response.parts:
                            for part in response.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    # Check if this is audio data
                                    if hasattr(part.inline_data, 'mime_type') and 'audio' in part.inline_data.mime_type:
                                        audio_data = part.inline_data.data
                                        self.logger.debug(f"Found audio in inline_data with mime type: {part.inline_data.mime_type}")
                                        break
                                        
                        # Suppress the warnings about non-text parts in the response
                        # These warnings are expected since we're using the audio API
                        
                        if audio_data:
                            # Process and send to Exotel
                            self.logger.info(f"Processing audio data of length: {len(audio_data)} bytes")
                            
                            # Debug audio saving removed to improve performance
                            self.logger.debug(f"Received audio data of length: {len(audio_data)} bytes")
                            
                            # Add the raw audio to our buffer
                            self.audio_buffer.extend(audio_data)
                            self.logger.debug(f"Added {len(audio_data)} bytes to audio buffer, total size now: {len(self.audio_buffer)} bytes")
                            
                            # Send audio when buffer reaches size threshold OR time threshold
                            current_time = time.time()
                            time_since_last_send = current_time - self.last_buffer_send_time
                            send_audio = (len(self.audio_buffer) >= self.buffer_threshold or 
                                         (len(self.audio_buffer) > 0 and time_since_last_send >= self.buffer_time_threshold))
                            
                            if send_audio:
                                self.audio_chunk_counter += 1
                                self.logger.debug(f"Sending audio chunk {self.audio_chunk_counter} ({len(self.audio_buffer)} bytes)")
                                
                                # Process the entire buffer
                                buffered_audio = bytes(self.audio_buffer)
                                
                                # Determine Gemini's output sample rate from first audio chunk if not already set
                                if self.gemini_output_sample_rate is None:
                                    # Use the known Gemini output sample rate from the reference implementation
                                    # This is more reliable than trying to detect it from chunk size
                                    self.gemini_output_sample_rate = GEMINI_OUTPUT_SAMPLE_RATE
                                    self.logger.info(f"Using Gemini output sample rate: {self.gemini_output_sample_rate} Hz")
                                
                                # Resample from Gemini's rate to Exotel's rate
                                resampled_audio = resample_audio(buffered_audio, self.gemini_output_sample_rate, EXOTEL_SAMPLE_RATE)
                                
                                # Debug audio saving removed to improve performance
                                self.logger.debug(f"Resampled audio to {len(resampled_audio)} bytes")
                                
                                # Clear the buffer after sending
                                self.audio_buffer.clear()
                                
                                # Reset the last buffer send time
                                self.last_buffer_send_time = time.time()
                                
                                base64_audio = base64.b64encode(resampled_audio).decode('utf-8')
                                
                                # Send to Exotel if the WebSocket is still open
                                self.logger.debug("Sending audio response to Exotel")
                                try:
                                    if not self.websocket.closed and self.stream_sid:
                                        # Increment sequence number for each message
                                        self.sequence_number += 1
                                        
                                        # Send to client
                                        await self.websocket.send(json.dumps({
                                            "event": "media",
                                            "sequence_number": self.sequence_number,
                                            "stream_sid": self.stream_sid,
                                            "media": {
                                                "payload": base64_audio
                                            }
                                        }))
                                        self.sequence_number += 1
                                        
                                        # Send a mark to help client track audio chunks
                                        await self.websocket.send(json.dumps({
                                            "event": "mark",
                                            "sequence_number": self.sequence_number,
                                            "stream_sid": self.stream_sid,
                                            "mark": {
                                                "name": f"audio_chunk_{self.audio_chunk_counter}"
                                            }
                                        }))
                                    else:
                                        self.logger.warning("WebSocket connection closed or stream_sid not set, cannot send audio response")
                                        # Exit the loop if the connection is closed
                                        return
                                except Exception as e:
                                    self.logger.error(f"Error sending audio response: {e}")
                                    import traceback
                                    traceback.print_exc()
                                except websockets.exceptions.ConnectionClosed:
                                    self.logger.warning("WebSocket connection closed while sending audio response")
                                    # Exit the loop if the connection is closed
                                    return
                        
                        # Handle text responses if any
                        if hasattr(response, 'text') and response.text:
                            text = response.text
                            self.logger.info(f"Gemini text response: {text}")
                except Exception as e:
                    self.logger.error(f"Error processing Gemini turn: {e}")
                    # Continue to the next turn if there's an error with this one
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in receive_from_gemini: {e}")
            raise
    
    async def cleanup(self):
        """Clean up resources used by this session."""
        self.logger.info("Cleaning up Gemini session")
        if self.gemini_session:
            try:
                await self.gemini_session.close()
                self.logger.info("Gemini session closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing Gemini session: {e}")


class ExotelGeminiBridge:
    """Main server class that manages WebSocket connections and Gemini sessions."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765, path: str = "/media"):
        """Initialize the ExotelGeminiBridge server.
        
        Args:
            host: Host address to bind the server to
            port: Port to listen on
            path: WebSocket endpoint path (Exotel expects /media)
        """
        self.host = host
        self.port = port
        self.path = path
        self.active_sessions: Dict[str, GeminiSession] = {}
        self.logger = logging.getLogger("ExotelGeminiBridge")
    
    async def handle_connection(self, websocket):
        """Handle a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        self.logger.info(f"New connection established. Session ID: {session_id}")
        
        # Create a new Gemini session for this connection
        gemini_session = GeminiSession(session_id, websocket)
        self.active_sessions[session_id] = gemini_session
        
        try:
            # Run the session until it completes or encounters an error
            await gemini_session.run()
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed for session {session_id}")
        except Exception as e:
            self.logger.error(f"Error in session {session_id}: {e}")
        finally:
            # Clean up the session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            self.logger.info(f"Session {session_id} removed from active sessions")
    
    async def start_server(self):
        """Start the WebSocket server."""
        self.logger.info(f"Starting Exotel-Gemini Bridge server on {self.host}:{self.port}{self.path}")
        
        # Create a WebSocket server with specific route handling for Exotel
        # Note: In some environments, the handler might be called with just the websocket parameter
        # So we need to make the path parameter optional
        async def handler(websocket, path=None):
            # If path is None, try to get it from the websocket object (depends on websockets version)
            if path is None:
                try:
                    path = websocket.path
                except AttributeError:
                    # If we can't get the path, assume it's the default path
                    path = self.path
            
            # Now handle the connection based on the path
            if path == self.path or path.endswith(self.path):
                await self.handle_connection(websocket)
            else:
                self.logger.warning(f"Received connection to unknown path: {path}")
                await websocket.close(1008, "Path not supported")
        
        async with websockets.serve(handler, self.host, self.port):
            # Keep the server running indefinitely
            await asyncio.Future()


# Main entry point
async def main():
    # Parse command line arguments
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Exotel-Gemini Bridge server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host address to bind to')
    parser.add_argument('--port', type=int, default=None, help='Port to listen on (overrides PORT env var)')
    parser.add_argument('--path', type=str, default='/media', help='WebSocket endpoint path')
    args = parser.parse_args()

    # Check if API key is available
    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY environment variable not set. Please set it and try again.")
        sys.exit(1)

    # Get port from environment variable (for Railway) or use command line argument or default
    port = args.port if args.port is not None else int(os.environ.get('PORT', DEFAULT_PORT))

    # Create and start the server
    server = ExotelGeminiBridge(host=args.host, port=port, path=args.path)
    logging.info(f"Starting server on {args.host}:{port}{args.path}")
    return await server.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise
