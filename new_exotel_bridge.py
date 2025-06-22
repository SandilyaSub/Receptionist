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
import sys
from typing import Dict, Optional

# For Python versions before 3.11, implement compatibility classes
if sys.version_info < (3, 11):
    # TaskGroup implementation for Python < 3.11
    class TaskGroup:
        """A simple TaskGroup implementation for Python versions before 3.11."""
        
        def __init__(self):
            self.tasks = set()
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.tasks:
                # Cancel all tasks if we're exiting with an exception
                if exc_type is not None:
                    for task in self.tasks:
                        if not task.done():
                            task.cancel()
                
                # Wait for all tasks to complete
                await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Re-raise the exception if there was one
            return False
            
        def create_task(self, coro):
            task = asyncio.create_task(coro)
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return task
    
    # Simple ExceptionGroup implementation for Python < 3.11
    class ExceptionGroup(Exception):
        """A simple ExceptionGroup implementation for Python versions before 3.11."""
        
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.exceptions = exceptions
    
    # Add the compatibility classes to asyncio namespace
    asyncio.TaskGroup = TaskGroup
    asyncio.ExceptionGroup = ExceptionGroup

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

# Create a custom filter to filter out specific log messages
class NonTextPartsFilter(logging.Filter):
    """Filter to remove warnings about non-text parts in Gemini responses."""
    def filter(self, record):
        # Filter out warnings about non-text parts in the response
        if 'non-text parts in the response' in record.getMessage():
            return False
        if 'inline_data' in record.getMessage():
            return False
        return True

# Apply the filter to all relevant loggers
for logger_name in ['google.genai', 'google.genai.text', 'root']:
    logger = logging.getLogger(logger_name)
    logger.addFilter(NonTextPartsFilter())

# Set the level for google.genai loggers to ERROR to reduce verbosity
logging.getLogger('google.genai').setLevel(logging.ERROR)
logging.getLogger('google.genai.text').setLevel(logging.ERROR)

# Also use warnings module to filter warnings
warnings.filterwarnings("ignore", message=".*non-text parts in the response.*")
warnings.filterwarnings("ignore", message=".*inline_data.*")
warnings.filterwarnings("ignore", category=UserWarning, module='google.genai')

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

# Initialize Gemini client with increased timeout
client = genai.Client(
    http_options={
        "api_version": "v1beta",
        "timeout": 60.0,  # Increase timeout to 60 seconds
    },
    api_key=GEMINI_API_KEY,
)

# Load system prompt from file
def load_system_prompt(tenant="bakery"):
    """Load system prompt from a file based on tenant.
    
    Args:
        tenant: The tenant identifier (e.g., 'bakery', 'saloon')
        
    Returns:
        The system prompt as a string
    """
    # Get the current script directory to use absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the prompts directory with absolute path
    prompts_dir = os.path.join(script_dir, "prompts")
    
    # Log the directories for debugging
    logging.info(f"Script directory: {script_dir}")
    logging.info(f"Prompts directory: {prompts_dir}")
    logging.info(f"Current working directory: {os.getcwd()}")
    
    # List all files in the prompts directory for debugging
    try:
        prompt_files = os.listdir(prompts_dir)
        logging.info(f"Available prompt files: {prompt_files}")
    except Exception as e:
        logging.error(f"Failed to list prompt files: {e}")
        prompt_files = []
    
    # Construct the prompt file path based on tenant
    prompt_path = os.path.join(prompts_dir, f"prompt-{tenant}.txt")
    logging.info(f"Attempting to load prompt from: {prompt_path}")
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
            logging.info(f"Successfully loaded system prompt for tenant '{tenant}' from {prompt_path}")
            return system_prompt
    except Exception as e:
        logging.error(f"Failed to load system prompt for tenant '{tenant}' from {prompt_path}: {e}")
        
        # Try the default bakery prompt if tenant is not bakery
        if tenant != "bakery":
            try:
                default_prompt_path = os.path.join(prompts_dir, "prompt-bakery.txt")
                logging.info(f"Attempting to load default prompt from: {default_prompt_path}")
                with open(default_prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read()
                    logging.info(f"Successfully loaded default bakery prompt for tenant '{tenant}' from {default_prompt_path}")
                    return system_prompt
            except Exception as e2:
                logging.error(f"Failed to load default bakery prompt: {e2}")
        
        # Return a basic fallback prompt if no files can be loaded
        fallback_prompt = f"You are a receptionist at a {tenant if tenant else 'bakery'}. Be polite and helpful."
        logging.warning(f"Using fallback prompt for tenant '{tenant}': {fallback_prompt}")
        return fallback_prompt

# Function to create Gemini configuration with tenant-specific prompt
def create_gemini_config(tenant="bakery"):
    """Create a Gemini configuration with tenant-specific prompt.
    
    Args:
        tenant: The tenant identifier (e.g., 'bakery', 'saloon')
        
    Returns:
        A LiveConnectConfig object with the tenant-specific prompt
    """
    # Load the tenant-specific prompt
    tenant_prompt = load_system_prompt(tenant)
    
    # Create and return the configuration
    return types.LiveConnectConfig(
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
            parts=[types.Part.from_text(text=tenant_prompt)],
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
    
    def __init__(self, session_id: str, websocket, tenant="bakery"):
        """
        Args:
            session_id: Unique identifier for this session
            websocket: WebSocket connection to communicate with the client
            tenant: The tenant identifier (e.g., 'bakery', 'saloon')
        """
        self.session_id = session_id
        self.websocket = websocket
        self.gemini_session = None
        self.tenant = tenant
        self.logger = logging.getLogger(f"GeminiSession-{tenant}-{session_id}")
        
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
        """Initialize the Gemini session with retry logic."""
        self.logger.info(f"Initializing Gemini session for tenant '{self.tenant}'")
        
        # Retry parameters
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second delay
        
        # Create tenant-specific configuration
        tenant_config = create_gemini_config(self.tenant)
        
        # Retry loop for initialization
        for attempt in range(max_retries):
            try:
                # Use async with to properly handle the AsyncGeneratorContextManager
                self.gemini_session = client.aio.live.connect(
                    model="models/gemini-2.5-flash-preview-native-audio-dialog",
                    config=tenant_config
                )
                self.logger.info(f"Gemini session initialized successfully for tenant '{self.tenant}'")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Gemini session initialization failed (attempt {attempt+1}/{max_retries}): {e}")
                    # Exponential backoff
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Double the delay for next attempt
                else:
                    self.logger.error(f"Gemini session initialization failed after {max_retries} attempts: {e}")
                    raise  # Re-raise the exception after all retries fail
    
    async def run(self):
        """Run the Gemini session, handling bidirectional audio streaming."""
        try:
            # First, wait for and process the 'start' message from the client
            # This ensures stream_sid is set before any audio processing begins
            await self.wait_for_start_message()
            
            # Only initialize Gemini after we have the stream_sid
            self.logger.info(f"Start message received with stream_sid={self.stream_sid}, initializing Gemini")
            await self.initialize()
            
            # Use async with to properly handle the Gemini session
            async with self.gemini_session as session:
                self.gemini_session = session
                self.logger.info("Gemini session connected")
                
                # Create tasks for bidirectional streaming
                async with asyncio.TaskGroup() as tg:
                    # Task 1: Continue receiving audio from Exotel and send to Gemini
                    tg.create_task(self.continue_receiving_from_exotel())
                    
                    # Task 2: Receive responses from Gemini and send to Exotel
                    tg.create_task(self.receive_from_gemini())
                    
                    # Task 3: Send keep-alive messages to prevent Exotel from timing out
                    tg.create_task(self.send_keep_alive_messages())
                
        except Exception as e:
            self.logger.error(f"Error in Gemini session: {e}")
            raise
        finally:
            await self.cleanup()
            
    async def wait_for_start_message(self):
        """Wait for and process the 'start' message from the client."""
        self.logger.info("Waiting for 'start' message from client")
        
        # Set a reasonable timeout for waiting for the start message
        start_timeout = 10  # seconds, reduced from 30 to fail faster if there's an issue
        
        # Define the inner function to process messages until we get a start message
        async def process_messages_until_start():
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.logger.info(f"Received message: {data['event'] if 'event' in data else 'unknown event'}")
                    
                    if "event" in data:
                        if data["event"] == "connected":
                            self.logger.info("Connected message received")
                            # Continue waiting for start message
                            
                        elif data["event"] == "start":
                            self.logger.info("Start message received")
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
                                return True  # Successfully processed start message
                except json.JSONDecodeError:
                    self.logger.warning("Received non-JSON message")
                except Exception as e:
                    self.logger.error(f"Error processing message during wait_for_start: {e}")
            
            # If we get here, the websocket was closed without receiving a start message
            return False
        
        try:
            # Wait for the start message with a timeout
            try:
                success = await asyncio.wait_for(process_messages_until_start(), timeout=start_timeout)
                if not success:
                    self.logger.error("WebSocket closed without receiving start message")
                    # Continue anyway but with no stream_sid
            except asyncio.TimeoutError:
                self.logger.error(f"Timed out waiting for start message after {start_timeout} seconds")
                # Continue anyway but with no stream_sid
                
            # If we didn't get a stream_sid, log a warning but continue
            if not self.stream_sid:
                self.logger.warning("No valid stream_sid received. Audio responses will not be sent to client.")
                
        except Exception as e:
            self.logger.error(f"Error in wait_for_start_message: {e}")
            # Continue anyway but with no stream_sid
    
    async def receive_from_exotel(self):
        """Receive audio from Exotel via WebSocket and send to Gemini.
        
        This is the original method that processes all messages. It's now split into
        two phases: wait_for_start_message and continue_receiving_from_exotel.
        """
        self.logger.info("Starting to receive audio from Exotel")
        
        # First wait for the start message
        await self.wait_for_start_message()
        
        # Then continue receiving audio and other messages
        await self.continue_receiving_from_exotel()
    
    async def continue_receiving_from_exotel(self):
        """Continue receiving audio from Exotel after the start message has been processed."""
        self.logger.info("Continuing to receive audio from Exotel")
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.logger.debug(f"Received message: {data['event'] if 'event' in data else 'unknown event'}")
                    
                    if "event" in data:
                        if data["event"] == "connected":
                            self.logger.info("Connected message received")
                            
                        elif data["event"] == "media":
                            # Process incoming audio data
                            if "media" in data and "payload" in data["media"]:
                                # Decode base64 audio data
                                audio_data = base64.b64decode(data["media"]["payload"])
                                sample_rate = data["media"].get("rate", 8000)  # Default to 8kHz if not specified
                                
                                # Resample audio to 24kHz for Gemini if needed
                                if sample_rate != GEMINI_SAMPLE_RATE:
                                    self.logger.debug(f"Resampling audio from {sample_rate}Hz to {GEMINI_SAMPLE_RATE}Hz")
                                    audio_data = resample_audio(audio_data, sample_rate, GEMINI_SAMPLE_RATE)
                                
                                # Send audio data to Gemini
                                if self.gemini_session:
                                    await self.gemini_session.send_realtime_input(audio=types.Blob(
                                        data=audio_data,
                                        mime_type="audio/pcm"
                                    ))
                                    self.logger.debug(f"Sent {len(audio_data)} bytes of audio to Gemini")
                                else:
                                    self.logger.warning("Cannot send audio to Gemini: session not initialized")
                            
                        elif data["event"] == "stop":
                            self.logger.info("Stop message received")
                            # Close the Gemini session gracefully
                            if self.gemini_session:
                                # For end-of-stream, we don't send any more audio
                                # The session will be closed in the cleanup method
                                self.logger.info("Received stop message, will close Gemini session")
                            break  # Exit the loop
                            
                        elif data["event"] == "mark":
                            self.logger.info(f"Mark message received: {data.get('mark', {})}")
                            # No specific action needed for mark event
                            
                        elif data["event"] == "clear":
                            self.logger.info("Clear message received")
                            # Clear our audio buffer
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
        """Receive responses from Gemini and send to Exotel."""
        self.logger.info("Starting to receive responses from Gemini")
        
        # Retry parameters
        max_retries = 3
        base_retry_delay = 1.0
        
        # We no longer need to wait for stream_sid here since we now ensure it's set
        # before initializing Gemini in the run() method
        self.logger.info(f"Using stream_sid: {self.stream_sid} for audio responses")
        
        try:
            # Process responses from Gemini with retry logic
            while True:
                # Check if WebSocket is still open
                websocket_open = True
                try:
                    # First try to check if it has an 'open' attribute
                    if hasattr(self.websocket, 'open'):
                        websocket_open = self.websocket.open
                    # Then try to check if it has a 'closed' attribute
                    elif hasattr(self.websocket, 'closed'):
                        websocket_open = not self.websocket.closed
                    # Finally try to check if it has a 'state' attribute
                    elif hasattr(self.websocket, 'state'):
                        websocket_open = self.websocket.state.name == 'OPEN'
                except Exception as e:
                    self.logger.warning(f"Error checking WebSocket state: {e}")
                    # Assume it's open if we can't check
                    websocket_open = True
                
                # If WebSocket is closed, stop processing
                if not websocket_open:
                    self.logger.info("Client WebSocket connection closed, stopping Gemini processing")
                    break
                
                retry_count = 0
                success = False
                send_audio = False
                
                # Retry loop for each turn
                while not success and retry_count < max_retries:
                    try:
                        # Get the next turn from Gemini
                        turn = self.gemini_session.receive()
                        self.logger.debug("Waiting for Gemini response turn")
                        
                        # Process responses in this turn
                        async for response in turn:
                            self.logger.debug(f"Received response from Gemini: {response}")
                            
                            # Extract audio data from response
                            audio_data = None
                            
                            # Check for data in response.data first
                            if hasattr(response, 'data') and response.data:
                                audio_data = response.data
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
                            
                            # Handle text responses if any
                            if hasattr(response, 'text') and response.text:
                                text = response.text
                                self.logger.info(f"Gemini text response: {text}")
                            
                            # Process audio data if found
                            if audio_data:
                                # Process and send to Exotel
                                self.logger.info(f"Processing audio data of length: {len(audio_data)} bytes")
                                
                                # Add the raw audio to our buffer
                                self.audio_buffer.extend(audio_data)
                                self.logger.debug(f"Added {len(audio_data)} bytes to audio buffer, total size now: {len(self.audio_buffer)} bytes")
                                
                                # Send audio when buffer reaches size threshold OR time threshold
                                current_time = time.time()
                                time_since_last_send = current_time - self.last_buffer_send_time
                                send_audio = (len(self.audio_buffer) >= self.buffer_threshold or 
                                             (len(self.audio_buffer) > 0 and time_since_last_send >= self.buffer_time_threshold))
                                
                                if send_audio:
                                    await self._send_audio_to_exotel()
                        
                        # If we got here without exceptions, the turn was successful
                        success = True
                        
                    except Exception as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            retry_delay = base_retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                            self.logger.warning(f"Error processing Gemini turn: {e}; retrying in {retry_delay} seconds (attempt {retry_count}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                        else:
                            self.logger.error(f"Error processing Gemini turn after {max_retries} attempts: {e}")
                            # Send any buffered audio before moving on
                            if len(self.audio_buffer) > 0:
                                try:
                                    await self._send_audio_to_exotel()
                                except Exception as audio_error:
                                    self.logger.error(f"Error sending buffered audio after Gemini error: {audio_error}")
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket connection closed, stopping Gemini processing")
            # Don't raise the exception, allow for graceful cleanup
        except Exception as e:
            self.logger.error(f"Error in receive_from_gemini: {e}")
            raise
    
    async def _send_audio_to_exotel(self):
        """Helper method to send buffered audio to Exotel"""
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
            # Check if WebSocket is open using a more compatible approach
            websocket_open = True
            try:
                # First try to check if it has an 'open' attribute
                if hasattr(self.websocket, 'open'):
                    websocket_open = self.websocket.open
                # Then try to check if it has a 'closed' attribute
                elif hasattr(self.websocket, 'closed'):
                    websocket_open = not self.websocket.closed
                # Finally try to check if it has a 'state' attribute
                elif hasattr(self.websocket, 'state'):
                    websocket_open = self.websocket.state.name == 'OPEN'
            except Exception as e:
                self.logger.warning(f"Error checking WebSocket state: {e}")
                # Assume it's open if we can't check
                websocket_open = True
                
            if not websocket_open:
                self.logger.warning("WebSocket connection is closed, cannot send audio response")
                return False
                
            if not self.stream_sid:
                self.logger.warning("stream_sid is not set, cannot send audio response. This may be due to not receiving a 'start' message from the client.")
                return False
                
            # If we get here, both websocket_open and self.stream_sid are valid
            # Increment sequence number for each message
            self.sequence_number += 1
            
            # Send to client
            await self.websocket.send(json.dumps({
                "event": "media",
                "sequence_number": str(self.sequence_number),
                "stream_sid": self.stream_sid,
                "media": {
                    "payload": base64_audio
                }
            }))
            self.sequence_number += 1
            
            # Send a mark to help client track audio chunks
            await self.websocket.send(json.dumps({
                "event": "mark",
                "sequence_number": str(self.sequence_number),
                "stream_sid": self.stream_sid,
                "mark": {
                    "name": f"audio_chunk_{self.audio_chunk_counter}"
                }
            }))
            
            self.logger.debug(f"Successfully sent audio chunk {self.audio_chunk_counter} to client with stream_sid {self.stream_sid}")
        except Exception as e:
            self.logger.error(f"Error sending audio response: {e}")
            import traceback
            traceback.print_exc()
            return False
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed while sending audio response")
            return False
            
        return True
    
    async def send_keep_alive_messages(self):
        """Send periodic keep-alive messages to prevent Exotel from timing out the connection."""
        self.logger.info("Starting keep-alive message task")
        keep_alive_interval = 2.0  # Send a keep-alive every 2 seconds
        keep_alive_counter = 0
        
        try:
            while True:
                # Check if WebSocket is still open
                websocket_open = True
                try:
                    if hasattr(self.websocket, 'open'):
                        websocket_open = self.websocket.open
                    elif hasattr(self.websocket, 'closed'):
                        websocket_open = not self.websocket.closed
                    elif hasattr(self.websocket, 'state'):
                        websocket_open = self.websocket.state.name == 'OPEN'
                except Exception as e:
                    self.logger.warning(f"Error checking WebSocket state in keep-alive: {e}")
                    websocket_open = True
                
                if not websocket_open:
                    self.logger.info("WebSocket closed, stopping keep-alive messages")
                    break
                    
                if not self.stream_sid:
                    self.logger.debug("stream_sid not set yet, waiting before sending keep-alive")
                    await asyncio.sleep(0.5)
                    continue
                
                # Send a keep-alive mark message
                keep_alive_counter += 1
                self.sequence_number += 1
                
                try:
                    await self.websocket.send(json.dumps({
                        "event": "mark",
                        "sequence_number": str(self.sequence_number),
                        "stream_sid": self.stream_sid,
                        "mark": {
                            "name": f"keep_alive_{keep_alive_counter}"
                        }
                    }))
                    self.logger.debug(f"Sent keep-alive message #{keep_alive_counter}")
                except Exception as e:
                    self.logger.warning(f"Failed to send keep-alive message: {e}")
                    # If we can't send a message, the connection might be closed
                    # Wait a bit before trying again
                    await asyncio.sleep(0.5)
                
                # Wait before sending the next keep-alive
                await asyncio.sleep(keep_alive_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Keep-alive task cancelled")
        except Exception as e:
            self.logger.error(f"Error in keep-alive task: {e}")
    
    async def cleanup(self):
        """Clean up resources for this session."""
        self.logger.info("Cleaning up Gemini session")
        
        # Close the Gemini session if it exists
        if self.gemini_session:
            try:
                # Close the session context manager if possible
                if hasattr(self.gemini_session, '__aexit__'):
                    await self.gemini_session.__aexit__(None, None, None)
                    self.logger.info("Gemini session closed successfully")
                else:
                    self.logger.info("Gemini session does not have __aexit__ method, skipping explicit close")
            except Exception as e:
                self.logger.error(f"Error closing Gemini session: {e}")
        
        # Clear the reference to avoid memory leaks
        self.gemini_session = None
        self.logger.info("Gemini session reference cleared")


class ExotelGeminiBridge:
    """Main server class that manages WebSocket connections and Gemini sessions."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765, base_path: str = "/"):
        """
        Initialize the ExotelGeminiBridge server.
        
        Args:
            host: Host address to bind the server to
            port: Port to listen on
            base_path: Base WebSocket endpoint path
        """
        self.host = host
        self.port = port
        self.base_path = base_path
        self.active_sessions: Dict[str, GeminiSession] = {}
        self.logger = logging.getLogger("ExotelGeminiBridge")
    
    async def handle_connection(self, websocket, path):
        """Handle a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            path: The WebSocket path requested by the client
        """
        # Parse the tenant from the path
        tenant = self._parse_tenant_from_path(path)
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        self.logger.info(f"New connection: {session_id} for tenant '{tenant}'")
        
        # Create a new session with the tenant
        session = GeminiSession(session_id, websocket, tenant)
        self.active_sessions[session_id] = session
        
        try:
            # Run the session
            await session.run()
        except websockets.exceptions.ConnectionClosed as e:
            self.logger.info(f"Connection closed: {session_id} - {e}")
        except Exception as e:
            self.logger.error(f"Error in session {session_id}: {e}")
        finally:
            # Clean up the session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            self.logger.info(f"Session ended: {session_id}")
            
    def _parse_tenant_from_path(self, path):
        """Parse the tenant from the WebSocket path.
        
        Args:
            path: The WebSocket path
            
        Returns:
            The tenant identifier (e.g., 'bakery', 'saloon')
        """
        # Log the raw path for debugging
        self.logger.info(f"Raw WebSocket path: '{path}'")
        
        # Remove leading and trailing slashes
        clean_path = path.strip('/')
        self.logger.info(f"Cleaned path: '{clean_path}'")
        
        # Split the path into segments
        segments = clean_path.split('/')
        self.logger.info(f"Path segments: {segments}")
        
        # If the path is empty or just 'media', use the default tenant
        if not segments or segments[0] == 'media' or segments[0] == '':
            self.logger.info(f"Using default tenant 'bakery' for path '{path}'")
            return 'bakery'  # Default tenant
        
        # Handle Railway's path format which might include the full URL
        if segments[0].startswith('http') or segments[0].startswith('ws'):
            self.logger.info(f"Detected full URL in path: '{segments[0]}'")
            # Extract the hostname part and look for tenant in the remaining segments
            if len(segments) > 1:
                tenant = segments[1]  # The tenant might be the second segment
                self.logger.info(f"Using second segment as tenant: '{tenant}'")
            else:
                self.logger.info(f"No tenant found in URL path, using default 'bakery'")
                tenant = 'bakery'
        else:
            # If the path is like '/bakery' or '/saloon', use that as the tenant
            tenant = segments[0]
            self.logger.info(f"Using first segment as tenant: '{tenant}'")
        
        # Validate the tenant against known tenants
        known_tenants = ['bakery', 'saloon']
        if tenant not in known_tenants:
            self.logger.warning(f"Unknown tenant '{tenant}', falling back to 'bakery'")
            tenant = 'bakery'
        
        # Log the final tenant detection
        self.logger.info(f"Final tenant detection: '{tenant}' from path '{path}'")
        
        return tenant
    
    async def start_server(self):
        """Start the WebSocket server."""
        self.logger.info(f"Starting multi-tenant Exotel-Gemini Bridge server on {self.host}:{self.port}{self.base_path}")
        
        # Create a WebSocket server
        async def handler(websocket, path=None):
            # If path is None, try to get it from the websocket object (depends on websockets version)
            if path is None:
                try:
                    path = websocket.path
                except AttributeError:
                    # If we can't get the path, assume it's the default path
                    path = '/media'
            
            # Handle the connection with the path
            await self.handle_connection(websocket, path)
        
        # Start the server
        server = await websockets.serve(
            handler,
            self.host,
            self.port
        )
        
        self.logger.info("Server started. Waiting for connections...")
        self.logger.info("Available tenant paths: /bakery, /saloon, /media (default: bakery)")
        
        # Keep the server running indefinitely
        await server.wait_closed()


# Main entry point
async def main():
    # Parse command line arguments
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Multi-tenant Exotel-Gemini Bridge server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host address to bind to')
    parser.add_argument('--port', type=int, default=None, help='Port to listen on (overrides PORT env var)')
    parser.add_argument('--base-path', type=str, default='/', help='Base WebSocket endpoint path')
    args = parser.parse_args()

    # Check if API key is available
    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY environment variable not set. Please set it and try again.")
        sys.exit(1)

    # Get port from environment variable (for Railway) or use command line argument or default
    port = args.port if args.port is not None else int(os.environ.get('PORT', DEFAULT_PORT))

    # Create and start the server
    server = ExotelGeminiBridge(host=args.host, port=port, base_path=args.base_path)
    await server.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise
