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
from datetime import datetime
from typing import Dict, Optional
import httpx


# Directory to store call transcripts
CALL_DETAILS_DIR = "call_details"

# Ensure the call_details directory exists
os.makedirs(CALL_DETAILS_DIR, exist_ok=True)

# TranscriptManager class for saving conversation transcripts and running analysis
class TranscriptManager:
    """Manages the conversation transcript, saves it, and runs analysis."""
    def __init__(self, session_id=None, call_sid=None, tenant=None, gemini_session=None):
        self.session_id = session_id or str(uuid.uuid4())
        self.call_sid = call_sid
        self.tenant = tenant
        self.gemini_session = gemini_session  # Reference to GeminiSession for conversation tokens
        self.transcript_data = {"session_id": self.session_id, "conversation": []}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.final_model_text = ""
        self.supabase_client = supabase
        
        # Initialize token accumulator if call_sid is available
        self.token_accumulator = None
        if self.call_sid:
            from ai_token_tracker import CallTokenAccumulator
            self.token_accumulator = CallTokenAccumulator(self.call_sid, self.logger)

    def add_to_transcript(self, role, text):
        """Adds a message to the transcript."""
        if text and text.strip():
            # Removed verbose logging statements
            self.transcript_data["conversation"].append({"role": role, "text": text.strip()})

    def _merge_consecutive_messages(self):
        """Merge consecutive messages from the same role before saving."""
        if not self.transcript_data.get("conversation"):
            return
            
        merged_conversation = []
        current_role = None
        current_text = ""
        
        for message in self.transcript_data["conversation"]:
            if message["role"] == current_role:
                # Same role, append to current text
                current_text += " " + message["text"]
            else:
                # Different role, save the previous message if it exists
                if current_role:
                    merged_conversation.append({"role": current_role, "text": current_text})
                # Start a new message
                current_role = message["role"]
                current_text = message["text"]
        
        # Add the last message
        if current_role:
            merged_conversation.append({"role": current_role, "text": current_text})
        
        # Replace the conversation with the merged version
        self.transcript_data["conversation"] = merged_conversation

    def get_full_transcript(self):
        """Returns the full transcript data."""
        return self.transcript_data

    async def save_transcript_and_analyze(self):
        """Saves the transcript, analyzes it, and updates the record in Supabase."""
        if not self.supabase_client:
            self.logger.error("Supabase client not initialized. Cannot process transcript.")
            return

        if not self.transcript_data.get("conversation"):
            self.logger.warning("No conversation to save, skipping transcript processing.")
            return

        # Add the final model text if it exists
        if self.final_model_text:
            self.add_to_transcript("assistant", self.final_model_text)
            self.final_model_text = ""
            
        # Merge consecutive messages from the same role before saving
        self._merge_consecutive_messages()

        record_id = None
        try:
            # Step 1: Insert the initial transcript data
            # Note: We don't include an 'id' field - let Supabase auto-generate it
            data_to_insert = {
                "session_id": self.session_id,
                "tenant": self.tenant,
                "transcript": self.transcript_data,
                "call_sid": self.call_sid
            }
            self.logger.info(f"Attempting to insert transcript for session {self.session_id} into 'call_details'.")
            response = self.supabase_client.table("call_details").insert(data_to_insert).execute()
            
            if response.data:
                record_id = response.data[0]['id']
                self.logger.info(f"Successfully saved transcript to Supabase with record ID: {record_id}")
            else:
                self.logger.error("Failed to insert transcript into Supabase, no data returned.")
                return

        except Exception as e:
            self.logger.error(f"Error saving initial transcript to Supabase: {e}")
            return # Stop if initial save fails

        # Extract conversation tokens from GeminiSession if available
        if self.gemini_session and self.token_accumulator:
            try:
                conversation_token_data = self.gemini_session.extract_total_conversation_tokens()
                if conversation_token_data:
                    # Add aggregated conversation tokens to the accumulator
                    self.token_accumulator.add_aggregated_conversation_tokens(conversation_token_data)
                    self.logger.info(f"Successfully added conversation tokens to accumulator: {conversation_token_data['total_tokens']} tokens")
                else:
                    self.logger.warning("No conversation tokens were collected during the session")
            except Exception as token_error:
                self.logger.error(f"Error extracting conversation tokens: {token_error}")
                # Continue with analysis even if token extraction fails

        try:
            # Step 2: Analyze the transcript (import locally to ensure config is loaded)
            from transcript_analyzer import analyze_transcript
            full_transcript_text = "\n".join([f"{turn['role']}: {turn['text']}" for turn in self.transcript_data["conversation"]])
            analysis_result = await analyze_transcript(full_transcript_text, self.tenant, GEMINI_API_KEY, self.token_accumulator)

            # Step 3: Update the record with the analysis results
            if analysis_result:
                self.logger.info(f"Updating record {record_id} with analysis results.")
                update_data = {
                    "call_type": analysis_result.get("call_type"),
                    "critical_call_details": analysis_result
                }
                self.supabase_client.table("call_details").update(update_data).eq("id", record_id).execute()
                self.logger.info(f"Successfully updated call_details for id {record_id} with analysis.")
                
                # Trigger the action service to send notifications
                try:
                    from action_service import ActionService
                    action_service = ActionService(logger=self.logger)
                    success = await action_service.process_call_actions(self.call_sid, self.tenant, self.token_accumulator)
                    if success:
                        self.logger.info(f"Successfully processed notifications for call {self.call_sid}")
                    else:
                        self.logger.warning(f"Some notifications failed for call {self.call_sid}")
                except Exception as action_error:
                    self.logger.error(f"Error processing notifications: {action_error}")
                    # Continue with cleanup even if notifications fail
                
                # Save accumulated token data to database at the end
                if self.token_accumulator:
                    try:
                        await self.token_accumulator.save_to_database()
                        self.logger.info(f"Successfully saved token usage data for call {self.call_sid}")
                    except Exception as token_error:
                        self.logger.error(f"Error saving token data: {token_error}")
                        # Continue with cleanup even if token save fails
            else:
                self.logger.warning(f"Analysis returned no result for record {record_id}. No update performed.")

        except Exception as e:
            self.logger.error(f"An error occurred during transcript analysis or DB update: {e}")
            import traceback
            traceback.print_exc()

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
from dotenv import load_dotenv
from supabase import create_client, Client

# Configure logging to both console and file
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# Create a file handler that logs to a new file each run
log_file = os.path.join(log_dir, f"exotel_bridge_{int(time.time())}.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Suppress verbose warnings from the Gemini library
logging.getLogger('google_genai').setLevel(logging.ERROR)

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)
logging.info(f"Attempting to load .env file from: {dotenv_path}")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY")

# Diagnostic logging for environment variables
if not SUPABASE_URL:
    logging.error("SUPABASE_URL not found. Please check your .env file.")
else:
    logging.info("SUPABASE_URL loaded successfully.")

if not SUPABASE_KEY:
    logging.error("SUPABASE_API_KEY not found. Please check your .env file.")
else:
    logging.info("SUPABASE_API_KEY loaded successfully.")

# Initialize Supabase client
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.info("Successfully connected to Supabase.")
    else:
        supabase = None
        raise ValueError("Supabase URL or Key is missing, cannot create client.")
except Exception as e:
    logging.error(f"Failed to initialize Supabase client: {e}")
    supabase = None

# Import language utilities
from language_utils import map_language_to_bcp47_code

# Tenant greeting configuration cache
tenant_greeting_cache = {}
CACHE_LOADED = False

async def load_tenant_greeting_configs():
    """Load all tenant greeting configurations into cache at startup.
    
    Returns:
        dict: Tenant greeting configurations keyed by tenant_id
    """
    global tenant_greeting_cache, CACHE_LOADED
    
    if not supabase:
        logging.warning("Supabase client not available, using empty greeting cache")
        return {}
    
    try:
        logging.info("Loading tenant greeting configurations...")
        
        # Fetch all active tenant greeting configs
        response = supabase.table('tenant_configs').select(
            'tenant_id, language, welcome_message'
        ).eq('is_active', True).execute()
        
        if response.data:
            for config in response.data:
                tenant_id = config.get('tenant_id')
                if tenant_id:
                    # Map language to BCP-47 code for Gemini Live API
                    language_bcp47 = map_language_to_bcp47_code(config.get('language', 'english'))
                    welcome_message = config.get('welcome_message')
                    
                    tenant_greeting_cache[tenant_id] = {
                        'language_bcp47': language_bcp47,
                        'welcome_message': welcome_message
                    }
                    
                    logging.info(f"Loaded greeting config for tenant '{tenant_id}': language_bcp47={language_bcp47}, has_custom_message={bool(welcome_message)}")
            
            CACHE_LOADED = True
            logging.info(f"Successfully loaded {len(tenant_greeting_cache)} tenant greeting configurations")
        else:
            logging.warning("No tenant greeting configurations found in database")
            
    except Exception as e:
        logging.error(f"Failed to load tenant greeting configurations: {e}")
        # Don't raise exception - we'll use defaults
    
    return tenant_greeting_cache

async def get_tenant_greeting_config(tenant_id: str) -> dict:
    """Get greeting configuration for a specific tenant.
    
    Args:
        tenant_id: The tenant identifier
        
    Returns:
        dict: Greeting configuration with 'language' and 'welcome_message' keys
    """
    global tenant_greeting_cache, CACHE_LOADED
    
    # If cache not loaded yet, try to load it
    if not CACHE_LOADED:
        await load_tenant_greeting_configs()
    
    # Check cache first
    if tenant_id in tenant_greeting_cache:
        config = tenant_greeting_cache[tenant_id]
        logging.info(f"Found cached greeting config for tenant '{tenant_id}': {config}")
        return config
    
    # If not in cache, try to fetch from database
    if supabase:
        try:
            logging.info(f"Fetching greeting config for tenant '{tenant_id}' from database...")
            response = supabase.table('tenant_configs').select(
                'language, welcome_message'
            ).eq('tenant_id', tenant_id).eq('is_active', True).execute()
            
            if response.data:
                config_data = response.data[0]
                language_bcp47 = map_language_to_bcp47_code(config_data.get('language', 'english'))
                welcome_message = config_data.get('welcome_message')
                
                config = {
                    'language_bcp47': language_bcp47,
                    'welcome_message': welcome_message
                }
                
                # Cache the result
                tenant_greeting_cache[tenant_id] = config
                logging.info(f"Fetched and cached greeting config for tenant '{tenant_id}': {config}")
                return config
        except Exception as e:
            logging.error(f"Failed to fetch greeting config for tenant '{tenant_id}': {e}")
    
    # Fallback to defaults
    default_config = {
        'language_bcp47': 'en-US',
        'welcome_message': None
    }
    
    logging.info(f"Using default greeting config for tenant '{tenant_id}': {default_config}")
    return default_config

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

# The client for analysis is now configured within the analyzer function itself.

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
    
    # Log the directory for debugging
    logging.debug(f"Script directory: {script_dir}")
    logging.debug(f"Current working directory: {os.getcwd()}")
    
    # Construct the prompt file path based on tenant
    prompt_path = os.path.join(os.path.dirname(__file__), 'tenant_repository', tenant, 'prompts', 'assistant.txt')
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
    # According to the official documentation at https://ai.google.dev/gemini-api/docs/live-guide
    # Using the simplest possible configuration to avoid payload errors
    logging.info("Creating Gemini Live API configuration with simplified settings")
    
    # Create a configuration with optimized VAD settings using the correct enum types
    # Following documentation at https://ai.google.dev/gemini-api/docs/live-guide#automatic-vad-configuration
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=tenant_prompt)],
            role="user"
        ),
        # Enable audio transcription as per https://ai.google.dev/gemini-api/docs/live-guide
        input_audio_transcription={},  # Empty dict enables input transcription
        output_audio_transcription={},  # Empty dict enables output transcription
        # Add VAD configuration for better short utterance detection using proper enums
        realtime_input_config={
            "automatic_activity_detection": {
                "disabled": False,  # Enable VAD
                "start_of_speech_sensitivity": types.StartSensitivity.START_SENSITIVITY_HIGH,  # More sensitive for telephony
                "end_of_speech_sensitivity": types.EndSensitivity.END_SENSITIVITY_HIGH,  # Faster end detection
                "prefix_padding_ms": 20,  # Default value
                "silence_duration_ms": 500  # Shorter silence to detect end of speech faster
            }
        }
    )
    
    # Log the configuration for debugging
    logging.info(f"Gemini configuration created for tenant '{tenant}'")
    
    return config

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
    """A session with Gemini for a single WebSocket connection."""
    
    def __init__(self, session_id, websocket, tenant="bakery"):
        """Initialize a new session.
        
        Args:
            session_id: A unique identifier for this session
            websocket: The WebSocket connection
            tenant: The tenant identifier (e.g., 'bakery', 'saloon')
        """
        self.session_id = session_id
        self.websocket = websocket
        self.tenant = tenant  # Store the initial tenant
        self.logger = logging.getLogger(f"GeminiSession-{session_id}")
        
        # Connection health monitoring
        self.connection_start_time = time.time()
        self.last_activity_time = time.time()
        self.gemini_response_times = []  # Track Gemini response latencies
        self.connection_state = "initializing"  # initializing -> active -> degraded -> failed
        
        # Will be initialized later
        self.gemini_session = None
        
        # Initialize state
        self.stream_sid = None
        self.call_sid = None
        self.account_sid = None
        self.sequence_number = 0
        self.audio_chunk_counter = 0
        self.is_speaking = False
        
        # Initialize transcript manager (will be properly set up after we get call_sid)
        self.transcript_manager = None
        
        # Audio buffer for combining chunks before sending to client
        self.audio_buffer = bytearray()
        self.buffer_threshold = 3840  # Smaller buffer, but still above Exotel's minimum (multiple of 320 bytes)
        self.min_chunk_size = 3840    # Ensure we never send less than this
        self.last_buffer_process_time = time.time()
        self.last_buffer_send_time = time.time()  # Initialize missing attribute
        self.buffer_time_threshold = 0.1  # Reduced time threshold for faster processing of short utterances
        
        # Will be detected from first audio chunk
        self.gemini_output_sample_rate = None
        self.gemini_output_channels = None
        
        # Conversation token tracking
        self.conversation_tokens = []  # Store all usage_metadata from conversation
    
    def extract_total_conversation_tokens(self):
        """Extract and sum up all conversation tokens from the session.
        
        Returns:
            dict: Token usage data for conversation, or None if no tokens were collected
        """
        if not self.conversation_tokens:
            self.logger.info(f"No conversation tokens collected for session {self.session_id}")
            return None
            
        try:
            # Initialize counters for detailed breakdown
            total_tokens = 0
            total_prompt_tokens = 0
            total_response_tokens = 0
            
            # Detailed breakdown by modality
            prompt_audio_tokens = 0
            prompt_text_tokens = 0
            response_audio_tokens = 0
            response_text_tokens = 0
            
            # Collect all breakdown details for final summary
            all_prompt_details = []
            all_response_details = []
            
            self.logger.debug(f"Processing {len(self.conversation_tokens)} usage_metadata objects for token extraction")
            
            for i, usage in enumerate(self.conversation_tokens):
                if usage is None:
                    self.logger.warning(f"Skipping None usage_metadata at index {i}")
                    continue
                    
                try:
                    # Get basic token counts (these are the reliable fields)
                    token_count = getattr(usage, 'total_token_count', None)
                    prompt_count = getattr(usage, 'prompt_token_count', None)
                    response_count = getattr(usage, 'response_token_count', None)
                    
                    # Add to totals
                    total_tokens += int(token_count) if token_count is not None else 0
                    total_prompt_tokens += int(prompt_count) if prompt_count is not None else 0
                    total_response_tokens += int(response_count) if response_count is not None else 0
                    
                    self.logger.debug(f"Usage {i}: total={token_count}, prompt={prompt_count}, response={response_count}")
                    
                    # Process prompt tokens details (input tokens by modality)
                    if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                        for detail in usage.prompt_tokens_details:
                            if detail is not None:
                                modality = str(getattr(detail, 'modality', 'unknown')).upper()
                                count = getattr(detail, 'token_count', 0)
                                count = int(count) if count is not None else 0
                                
                                if modality == 'AUDIO':
                                    prompt_audio_tokens += count
                                elif modality == 'TEXT':
                                    prompt_text_tokens += count
                                
                                all_prompt_details.append({
                                    "modality": modality,
                                    "count": count
                                })
                    
                    # Process response tokens details (output tokens by modality)
                    if hasattr(usage, 'response_tokens_details') and usage.response_tokens_details:
                        for detail in usage.response_tokens_details:
                            if detail is not None:
                                modality = str(getattr(detail, 'modality', 'unknown')).upper()
                                count = getattr(detail, 'token_count', 0)
                                count = int(count) if count is not None else 0
                                
                                if modality == 'AUDIO':
                                    response_audio_tokens += count
                                elif modality == 'TEXT':
                                    response_text_tokens += count
                                
                                all_response_details.append({
                                    "modality": modality,
                                    "count": count
                                })
                                
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Error processing usage_metadata at index {i}: {e}")
                    continue
            
            # Calculate input/output tokens based on breakdown
            # Input tokens = prompt tokens (both audio and text)
            input_tokens = total_prompt_tokens
            # Output tokens = response tokens (both audio and text)
            output_tokens = total_response_tokens
            
            conversation_token_data = {
                "model": "gemini-2.5-flash-preview-native-audio-dialog",
                "total_tokens": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "prompt_tokens": total_prompt_tokens,
                "response_tokens": total_response_tokens,
                "breakdown": {
                    "prompt_audio_tokens": prompt_audio_tokens,
                    "prompt_text_tokens": prompt_text_tokens,
                    "response_audio_tokens": response_audio_tokens,
                    "response_text_tokens": response_text_tokens
                }
            }
            
            # Add detailed breakdown arrays if we have data
            if all_prompt_details:
                conversation_token_data["prompt_details"] = all_prompt_details
            if all_response_details:
                conversation_token_data["response_details"] = all_response_details
            
            self.logger.info(f"Extracted conversation tokens for session {self.session_id}: {total_tokens} total ({input_tokens} input, {output_tokens} output) from {len(self.conversation_tokens)} usage reports")
            self.logger.debug(f"Token breakdown - Prompt Audio: {prompt_audio_tokens}, Prompt Text: {prompt_text_tokens}, Response Audio: {response_audio_tokens}, Response Text: {response_text_tokens}")
            
            return conversation_token_data
            
        except Exception as e:
            self.logger.error(f"Error extracting conversation tokens for session {self.session_id}: {str(e)}")
            return None

    def extract_greeting_from_prompt(self, prompt_text):
        """Extract greeting message from system prompt text.
        
        Args:
            prompt_text: The system prompt content
            
        Returns:
            Extracted greeting message or fallback
        """
        try:
            # Look for common greeting patterns in prompts
            patterns = [
                # Pattern 1: "Namaste! Welcome to..." (bakery style)
                r'"(Namaste!\s+Welcome\s+to[^"]+)"',
                # Pattern 2: "Namaste! This is Aarohi from..." (saloon style)
                r'"(Namaste!\s+This\s+is\s+Aarohi[^"]+)"',
                # Pattern 3: "Namaste! You've reached..." (joy_invite style)
                r'"(Namaste!\s+You\'ve\s+reached[^"]+)"',
                # Pattern 4: Any quoted greeting starting with Namaste
                r'"(Namaste![^"]+)"',
                # Pattern 5: SAMPLE INTERACTION FLOW pattern
                r'SAMPLE\s+INTERACTION\s+FLOW:\s*"([^"]+)"',
                # Pattern 6: Default greeting pattern
                r'start\s+with:\s*"([^"]+)"',
                r'greet\s+with:\s*"([^"]+)"'
            ]
            
            for pattern in patterns:
                import re
                match = re.search(pattern, prompt_text, re.IGNORECASE | re.DOTALL)
                if match:
                    greeting = match.group(1).strip()
                    self.logger.info(f"Extracted greeting from prompt: {greeting}")
                    return greeting
            
            # If no pattern matches, look for any greeting instruction
            # Look for lines containing greeting-related keywords
            lines = prompt_text.split('\n')
            for line in lines:
                line = line.strip()
                if any(keyword in line.lower() for keyword in ['greeting', 'welcome', 'namaste', 'hello']):
                    # Try to extract quoted text from this line
                    quote_match = re.search(r'"([^"]+)"', line)
                    if quote_match:
                        greeting = quote_match.group(1).strip()
                        self.logger.info(f"Found greeting in line: {greeting}")
                        return greeting
            
            self.logger.warning(f"No greeting pattern found in prompt for tenant '{self.tenant}'")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting greeting from prompt: {e}")
            return None
    
    async def send_dynamic_initial_greeting(self):
        """Send tenant-specific initial greeting extracted from system prompt."""
        try:
            # Load the same prompt that's used in Gemini configuration
            prompt_text = load_system_prompt(self.tenant)
            
            # Extract greeting from the prompt
            greeting_message = self.extract_greeting_from_prompt(prompt_text)
            
            # Use extracted greeting or fallback
            if greeting_message:
                self.logger.info(f"Using extracted greeting for tenant '{self.tenant}': {greeting_message}")
            else:
                greeting_message = "Hello there. My name is Aarohi. How may I help you today?"
                self.logger.info(f"Using fallback greeting for tenant '{self.tenant}': {greeting_message}")
            
            # Send the greeting message to Gemini
            await self.gemini_session.send_client_content(
                turns={"parts": [{"text": greeting_message}]}
            )
            
            # Add to transcript
            if self.transcript_manager:
                self.transcript_manager.add_to_transcript("assistant", greeting_message)
            
            self.logger.info(f"✅ Dynamic initial greeting sent successfully for tenant '{self.tenant}'")
            
        except Exception as e:
            self.logger.error(f"Failed to send dynamic greeting: {e}")
            # Fallback to basic greeting
            try:
                fallback_message = "Hello there. My name is Aarohi. How may I help you today?"
                await self.gemini_session.send_client_content(
                    turns={"parts": [{"text": fallback_message}]}
                )
                if self.transcript_manager:
                    self.transcript_manager.add_to_transcript("assistant", fallback_message)
                self.logger.info("✅ Fallback greeting sent successfully")
            except Exception as fallback_error:
                self.logger.error(f"Failed to send fallback greeting: {fallback_error}")
    
    def print_token_summary(self):
        """Print a comprehensive token usage summary for debugging purposes."""
        if not self.conversation_tokens:
            self.logger.info(f"No conversation tokens collected for session {self.session_id}")
            return
            
        self.logger.info(f"\n=== TOKEN USAGE SUMMARY FOR SESSION {self.session_id} ===")
        self.logger.info(f"Total usage reports collected: {len(self.conversation_tokens)}")
        
        # Get the aggregated token data
        token_data = self.extract_total_conversation_tokens()
        if token_data:
            self.logger.info(f"\n--- AGGREGATED TOTALS ---")
            self.logger.info(f"Total Tokens: {token_data['total_tokens']}")
            self.logger.info(f"Input Tokens: {token_data['input_tokens']}")
            self.logger.info(f"Output Tokens: {token_data['output_tokens']}")
            self.logger.info(f"Prompt Tokens: {token_data['prompt_tokens']}")
            self.logger.info(f"Response Tokens: {token_data['response_tokens']}")
            
            if 'breakdown' in token_data:
                breakdown = token_data['breakdown']
                self.logger.info(f"\n--- MODALITY BREAKDOWN ---")
                self.logger.info(f"Prompt Audio Tokens: {breakdown['prompt_audio_tokens']}")
                self.logger.info(f"Prompt Text Tokens: {breakdown['prompt_text_tokens']}")
                self.logger.info(f"Response Audio Tokens: {breakdown['response_audio_tokens']}")
                self.logger.info(f"Response Text Tokens: {breakdown['response_text_tokens']}")
            
            # Cost estimation based on Google's pricing
            # Input audio: $3.00/1M tokens, Output audio: $12.00/1M tokens
            # Text tokens: $0.30/1M for input, $1.20/1M for output (approximate)
            if 'breakdown' in token_data:
                breakdown = token_data['breakdown']
                input_audio_cost = (breakdown['prompt_audio_tokens'] / 1_000_000) * 3.00
                output_audio_cost = (breakdown['response_audio_tokens'] / 1_000_000) * 12.00
                input_text_cost = (breakdown['prompt_text_tokens'] / 1_000_000) * 0.30
                output_text_cost = (breakdown['response_text_tokens'] / 1_000_000) * 1.20
                total_cost = input_audio_cost + output_audio_cost + input_text_cost + output_text_cost
                
                self.logger.info(f"\n--- ESTIMATED COSTS (USD) ---")
                self.logger.info(f"Input Audio Cost: ${input_audio_cost:.6f}")
                self.logger.info(f"Output Audio Cost: ${output_audio_cost:.6f}")
                self.logger.info(f"Input Text Cost: ${input_text_cost:.6f}")
                self.logger.info(f"Output Text Cost: ${output_text_cost:.6f}")
                self.logger.info(f"Total Estimated Cost: ${total_cost:.6f}")
        
        self.logger.info(f"\n--- RAW USAGE DATA ---")
        for i, usage in enumerate(self.conversation_tokens):
            if usage:
                total = getattr(usage, 'total_token_count', 'N/A')
                prompt = getattr(usage, 'prompt_token_count', 'N/A')
                response = getattr(usage, 'response_token_count', 'N/A')
                self.logger.info(f"Usage {i}: Total={total}, Prompt={prompt}, Response={response}")
        
        self.logger.info(f"=== END TOKEN SUMMARY ===")
    
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
                # Log the model being used
                model_name = "models/gemini-2.5-flash-preview-native-audio-dialog"
                self.logger.info(f"Connecting to Gemini model: {model_name}")
                
                # Use async with to properly handle the AsyncGeneratorContextManager
                self.gemini_session = client.aio.live.connect(
                    model=model_name,
                    config=tenant_config
                )
                
                self.logger.info(f"Gemini session initialized successfully for tenant '{self.tenant}'")
                return
            except Exception as e:
                error_message = str(e)
                self.logger.error(f"Gemini session initialization error details: {error_message}")
                
                if "invalid frame payload data" in error_message:
                    self.logger.error("WebSocket payload error detected. This may be due to invalid configuration parameters.")
                
                if attempt < max_retries - 1:
                    self.logger.warning(f"Gemini session initialization failed (attempt {attempt+1}/{max_retries}). Retrying...")
                    # Exponential backoff
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Double the delay for next attempt
                else:
                    self.logger.error(f"Gemini session initialization failed after {max_retries} attempts.")
                    raise  # Re-raise the exception after all retries fail
    
    async def run(self):
        """Run the session."""
        self.logger.info("Waiting for 'start' message from client")
        
        try:
            # Wait for the start message
            message = await self.websocket.recv()
            self.logger.info(f"Received message: {message}")
            
            # Parse the message
            data = json.loads(message)
            
            # Check if it's a connected message (might come first in some clients)
            if data.get("event") == "connected":
                self.logger.info("Connected message received")
                
                # Wait for the next message (should be start)
                message = await self.websocket.recv()
                self.logger.info(f"Received message: {message}")
                data = json.loads(message)
            
            # Check if it's a start message
            if data.get("event") == "start":
                self.logger.info("Start message received")
                
                # Extract stream_sid, call_sid, and account_sid
                start_data = data.get("start", {})
                self.stream_sid = start_data.get("stream_sid")
                self.call_sid = start_data.get("call_sid")
                self.account_sid = start_data.get("account_sid")
                
                # Check for tenant in custom_parameters
                if "custom_parameters" in start_data and "tenant" in start_data["custom_parameters"]:
                    new_tenant = start_data["custom_parameters"]["tenant"]
                    self.logger.info(f"Using tenant '{new_tenant}' from custom_parameters")
                    self.tenant = new_tenant
                else:
                    self.logger.info(f"No tenant specified in custom_parameters, using default tenant '{self.tenant}'")
                
                self.logger.info(f"Final tenant determination: {self.tenant}")
                
                
                self.logger.info(f"Stream started: stream_sid={self.stream_sid}, call_sid={self.call_sid}")
                
                # Initialize the transcript manager with call details
                if self.call_sid:
                    self.logger.info(f"Initializing transcript manager for call {self.call_sid}")

                    
                    # Create transcript manager with call details
                    self.transcript_manager = TranscriptManager(
                        call_sid=self.call_sid,
                        session_id=self.session_id,
                        tenant=self.tenant,
                        gemini_session=self
                    )
                    
                    # Ensure call_details directory exists
                    os.makedirs(CALL_DETAILS_DIR, exist_ok=True)

                else:
                    self.logger.warning("No call_sid received, transcript will not be saved")

                
                # Initialize Gemini session with the tenant (possibly updated from message)
                self.logger.info(f"Initializing Gemini session for tenant '{self.tenant}'")
                await self.initialize()
                
                try:
                    # Use async with to properly handle the Gemini session
                    async with self.gemini_session as session:
                        self.gemini_session = session
                        self.logger.info("Gemini session connected")
                        
                        # Send dynamic initial greeting based on tenant configuration
                        await self.send_dynamic_initial_greeting()
                        
                        # Create tasks for bidirectional streaming
                        async with asyncio.TaskGroup() as tg:
                            # Task 1: Continue receiving audio from Exotel and send to Gemini
                            tg.create_task(self.continue_receiving_from_exotel())
                            
                            # Task 2: Receive responses from Gemini and send to Exotel
                            tg.create_task(self.receive_from_gemini())
                            
                            # Task 3: Send keep-alive messages to prevent Exotel from timing out
                            tg.create_task(self.send_keep_alive_messages())
                finally:
                    # Always call cleanup to ensure transcript is saved
                    try:
                        self.logger.info(f"Triggering cleanup for session {self.session_id}")
                        self.cleanup()
                        self.logger.info(f"Cleanup triggered for session {self.session_id}")
                    except Exception as cleanup_error:
                        self.logger.error(f"Error during cleanup: {cleanup_error}")
                        import traceback
                        traceback.print_exc()
            else:
                self.logger.error(f"Expected 'start' event, got: {data.get('event')}")
        except Exception as e:
            self.logger.error(f"Error in Gemini session: {e}")
            import traceback
            traceback.print_exc()
            # Even on error, try to save the transcript
            try:
                self.cleanup()
            except Exception as cleanup_error:
                self.logger.error(f"Error during cleanup after exception: {cleanup_error}")
                traceback.print_exc()
    
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
                                
                                # Check if tenant is specified in custom_parameters and update if valid
                                if self.custom_parameters and "tenant" in self.custom_parameters:
                                    custom_tenant = self.custom_parameters["tenant"]
                                    # Verify tenant exists in repository
                                    tenant_prompt_path = os.path.join(TENANT_REPOSITORY_DIR, custom_tenant, "prompts", "assistant.txt")
                                    if os.path.exists(tenant_prompt_path):
                                        self.logger.info(f"Updating tenant from '{self.tenant}' to '{custom_tenant}' based on custom_parameters")
                                        self.tenant = custom_tenant
                                    else:
                                        self.logger.warning(f"Tenant '{custom_tenant}' specified in custom_parameters does not have a valid prompt file. Using '{self.tenant}' instead.")
                                
                                # Initialize transcript manager for this session
                                self.logger.info("Creating transcript manager")
                                print(f"DEBUG: Creating transcript manager for call_sid: {self.call_sid}")
                                self.transcript_manager = TranscriptManager(
                                    call_sid=self.call_sid,
                                    session_id=self.session_id,
                                    tenant=self.tenant,
                                    gemini_session=self
                                )
                                self.logger.info(f"Transcript manager initialized for call_id: {self.call_sid}")
                                print(f"DEBUG: Transcript manager initialized for call_id: {self.call_sid}")
                                
                                # Verify call_details directory exists
                                if os.path.exists(CALL_DETAILS_DIR):
                                    print(f"DEBUG: Call details directory exists at {os.path.abspath(CALL_DETAILS_DIR)}")
                                else:
                                    print(f"DEBUG: Call details directory does not exist at {os.path.abspath(CALL_DETAILS_DIR)}")
                                    os.makedirs(CALL_DETAILS_DIR, exist_ok=True)
                                    print(f"DEBUG: Created call details directory at {os.path.abspath(CALL_DETAILS_DIR)}")
                                
                                # List files in call_details directory
                                print(f"DEBUG: Files in call_details directory: {os.listdir(CALL_DETAILS_DIR)}")
                                
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
        finally:
            # This block is critical. It runs when the `async for` loop exits,
            # which happens when the Exotel connection closes.
            self.logger.info("Exotel listening loop finished. Actively closing Gemini session to prevent timeout.")
            if self.gemini_session:
                await self.gemini_session.close()
    
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
                            
                            # Track conversation tokens if usage_metadata is available
                            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                                self.conversation_tokens.append(response.usage_metadata)
                                
                                # Enhanced token logging based on cookbook findings
                                usage = response.usage_metadata
                                self.logger.debug(f"Token usage details - Type: {type(usage)}")
                                
                                # Log all available attributes for debugging
                                attrs = [attr for attr in dir(usage) if not attr.startswith('_')]
                                self.logger.debug(f"Available usage_metadata attributes: {attrs}")
                                
                                # Log basic token counts
                                total_tokens = getattr(usage, 'total_token_count', None)
                                input_tokens = getattr(usage, 'input_token_count', None) or getattr(usage, 'input_tokens', None)
                                output_tokens = getattr(usage, 'output_token_count', None) or getattr(usage, 'output_tokens', None)
                                prompt_tokens = getattr(usage, 'prompt_token_count', None)
                                response_tokens = getattr(usage, 'response_token_count', None)
                                
                                self.logger.debug(f"Basic token counts - Total: {total_tokens}, Input: {input_tokens}, Output: {output_tokens}, Prompt: {prompt_tokens}, Response: {response_tokens}")
                                
                                # Log detailed breakdown if available
                                if hasattr(usage, 'prompt_tokens_details'):
                                    prompt_details = usage.prompt_tokens_details
                                    self.logger.debug(f"Prompt tokens details: {prompt_details}")
                                    if prompt_details:
                                        for detail in prompt_details:
                                            if detail:
                                                modality = getattr(detail, 'modality', 'unknown')
                                                count = getattr(detail, 'token_count', 0)
                                                self.logger.debug(f"  Prompt - Modality: {modality}, Tokens: {count}")
                                
                                if hasattr(usage, 'response_tokens_details'):
                                    response_details = usage.response_tokens_details
                                    self.logger.debug(f"Response tokens details: {response_details}")
                                    if response_details:
                                        for detail in response_details:
                                            if detail:
                                                modality = getattr(detail, 'modality', 'unknown')
                                                count = getattr(detail, 'token_count', 0)
                                                self.logger.debug(f"  Response - Modality: {modality}, Tokens: {count}")
                                
                                self.logger.debug(f"Accumulated conversation token data: {total_tokens} total tokens")
                            
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
                                if self.transcript_manager:
                                    self.transcript_manager.add_to_transcript("assistant", text)
                                else:
                                    self.logger.warning("Cannot add text to transcript: transcript_manager is None")
                                    
                            # Process input audio transcription (user speech)
                            if hasattr(response, 'server_content'):
                                self.logger.debug(f"Server content attributes: {dir(response.server_content)}")
                                
                                # Check for input transcription
                                has_input = hasattr(response.server_content, 'input_transcription')
                                self.logger.debug(f"Has input_transcription attribute: {has_input}")
                                
                                if has_input and response.server_content.input_transcription:
                                    self.logger.debug(f"Input transcription detected: {response.server_content.input_transcription}")
                                    user_text = response.server_content.input_transcription.text
                                    # User transcript is now handled by TranscriptManager
                                    if self.transcript_manager:
                                        self.transcript_manager.add_to_transcript("user", user_text)
                                    else:
                                        self.logger.warning("Cannot add user text to transcript: transcript_manager is None")
                                    
                                # Check for output transcription
                                has_output = hasattr(response.server_content, 'output_transcription')
                                self.logger.debug(f"Has output_transcription attribute: {has_output}")
                                
                                if has_output and response.server_content.output_transcription:
                                    self.logger.debug(f"Output transcription detected: {response.server_content.output_transcription}")
                                    model_text = response.server_content.output_transcription.text
                                    # Model transcript is now handled by TranscriptManager
                                    if self.transcript_manager:
                                        self.transcript_manager.add_to_transcript("assistant", model_text)
                                    else:
                                        self.logger.warning("Cannot add model text to transcript: transcript_manager is None")
                            else:
                                self.logger.debug("Response has no server_content attribute")
                            
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
        
        # Check if buffer size meets minimum chunk size requirement
        buffer_size = len(self.audio_buffer)
        self.logger.debug(f"Sending audio chunk {self.audio_chunk_counter} ({buffer_size} bytes)")
        
        if buffer_size < self.min_chunk_size:
            self.logger.debug(f"Buffer size {buffer_size} is below minimum chunk size {self.min_chunk_size}, padding buffer")
            # Pad with silence to reach minimum chunk size (zeros for PCM audio)
            padding_needed = self.min_chunk_size - buffer_size
            self.audio_buffer.extend(bytes(padding_needed))
            self.logger.debug(f"Added {padding_needed} bytes of padding, new buffer size: {len(self.audio_buffer)} bytes")
        
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
        self.logger.info("Starting enhanced keep-alive message task")
        keep_alive_interval = 30.0  # Increased from 10s to 30s for better stability
        keep_alive_counter = 0
        consecutive_failures = 0
        max_consecutive_failures = 3
        
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
                
                # Retry logic for sending keep-alive
                retry_count = 0
                max_retries = 3
                send_success = False
                
                while retry_count < max_retries and not send_success:
                    try:
                        send_start_time = time.time()
                        await self.websocket.send(json.dumps({
                            "event": "mark",
                            "sequence_number": str(self.sequence_number),
                            "stream_sid": self.stream_sid,
                            "mark": {
                                "name": f"keep_alive_{keep_alive_counter}",
                                "timestamp": time.time()
                            }
                        }))
                        send_duration = time.time() - send_start_time
                        
                        self.logger.debug(f"Sent keep-alive message #{keep_alive_counter} (attempt {retry_count + 1}, took {send_duration:.3f}s)")
                        send_success = True
                        consecutive_failures = 0  # Reset failure counter on success
                        
                    except Exception as e:
                        retry_count += 1
                        consecutive_failures += 1
                        
                        if retry_count < max_retries:
                            retry_delay = min(2 ** (retry_count - 1), 5)  # Exponential backoff, max 5s
                            self.logger.warning(f"Keep-alive send failed (attempt {retry_count}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                        else:
                            self.logger.error(f"Keep-alive send failed after {max_retries} attempts: {e}")
                
                # Check if we've had too many consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(f"Too many consecutive keep-alive failures ({consecutive_failures}). Connection may be unstable.")
                    # Don't break here - let the WebSocket timeout handle the disconnection
                    # This gives us better observability without being too aggressive
                
                # Wait before sending the next keep-alive
                await asyncio.sleep(keep_alive_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Keep-alive task cancelled")
        except Exception as e:
            self.logger.error(f"Error in keep-alive task: {e}")
        finally:
            self.logger.info(f"Keep-alive task ended. Sent {keep_alive_counter} messages, {consecutive_failures} consecutive failures at end.")
    
    def cleanup(self):
        """Triggers the non-blocking, asynchronous cleanup process."""
        self.logger.info(f"Triggering async cleanup for session {self.session_id}")
        asyncio.create_task(self.run_post_call_processing())

    async def run_post_call_processing(self):
        """Runs all post-call tasks in the background without blocking."""
        self.logger.info(f"Starting background post-call processing for {self.session_id}")
        
        # Print detailed token summary for debugging
        self.print_token_summary()

        # 1. Fetch and store Exotel call details first - needed for notifications
        if self.call_sid:
            self.logger.info(f"Fetching Exotel call details first for call_sid: {self.call_sid}")
            await self.fetch_and_store_exotel_details()
        else:
            self.logger.warning("No call_sid available, skipping Exotel detail fetch.")

        # 2. Save the transcript and analyze it
        if self.transcript_manager:
            self.logger.info("Saving transcript and analyzing...")
            await self.transcript_manager.save_transcript_and_analyze()
        else:
            self.logger.warning("No transcript manager available, skipping transcript save and analysis.")
        
        # (Placeholder for the next step)
        # await self.analyze_transcript_for_booking()

        # 3. Final resource cleanup - check for attribute existence first
        if hasattr(self, 'audio_stream') and self.audio_stream and not self.audio_stream.is_stopped():
            self.logger.info("Closing audio stream.")
            self.audio_stream.close()
            self.audio_stream = None

        if hasattr(self, 'gemini_session') and self.gemini_session:
            self.logger.info("Closing Gemini session.")
            await self.gemini_session.close()
            self.gemini_session = None

        self.logger.info(f"Background post-call processing finished for {self.session_id}")

    async def fetch_and_store_exotel_details(self):
        """Fetches call details from Exotel and stores them in Supabase."""
        self.logger.info(f"Fetching Exotel call details for call_sid: {self.call_sid}")
        
        api_key = os.environ.get("EXOTEL_API_KEY_USERNAME")
        api_token = os.environ.get("EXOTEL_API_KEY_PASSWORD")
        account_sid = os.environ.get("EXOTEL_ACCOUNT_SID")

        if not all([api_key, api_token, account_sid]):
            self.logger.error("Exotel API credentials or Account SID are not configured.")
            return

        url = f"https://api.exotel.com/v1/Accounts/{account_sid}/Calls/{self.call_sid}.json"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, auth=(api_key, api_token))
                response.raise_for_status() # Raises an exception for 4XX/5XX responses
                
                call_details = response.json().get("Call")
                if not call_details:
                    self.logger.error("Exotel API response did not contain 'Call' details.")
                    return

                # Prepare data for Supabase
                # Note: We don't include an 'id' field - let Supabase auto-generate it
                data_to_insert = {
                    "call_sid": self.call_sid,
                    "from_number": call_details.get("From"),
                    "to_number": call_details.get("To"),
                    "status": call_details.get("Status"),
                    "start_time": call_details.get("StartTime"),
                    "end_time": call_details.get("EndTime"),
                    "duration": call_details.get("Duration"),
                    "price": call_details.get("Price"),
                    "direction": call_details.get("Direction"),
                    "recording_url": call_details.get("RecordingUrl")
                }

                # Insert into Supabase
                if supabase:
                    self.logger.info(f"Inserting call details into Supabase for call_sid: {self.call_sid}")
                    supabase.table("exotel_call_details").insert(data_to_insert).execute()
                    self.logger.info("Successfully saved Exotel call details to Supabase.")
                else:
                    self.logger.error("Supabase client not available to save Exotel details.")

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error fetching Exotel details: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while fetching Exotel details: {e}")

        # Close the Gemini session if it exists
        if self.gemini_session:
            try:
                await self.gemini_session.close()
                self.logger.info("Gemini session closed")
                self.logger.debug(f"Gemini session closed for {self.session_id}")
            except Exception as e:
                self.logger.error(f"Error closing Gemini session: {e}")
                self.logger.debug(f"Error closing Gemini session: {e}")
                import traceback
                traceback.print_exc()
        
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
        
        # Ensure call_details directory exists at startup
        try:
            os.makedirs(CALL_DETAILS_DIR, exist_ok=True)
            self.logger.info(f"Created call_details directory at {os.path.abspath(CALL_DETAILS_DIR)}")
        except Exception as e:
            self.logger.error(f"Failed to create call_details directory: {e}")
            import traceback
            traceback.print_exc()
    
    async def handle_connection(self, websocket, path, tenant=None):
        """Handle a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            path: The WebSocket path
            tenant: Optional explicit tenant identifier. If None, will be parsed from path.
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Parse the tenant from the path if not explicitly provided
        if tenant is None:
            tenant = self._parse_tenant_from_path(path)
            self.logger.info(f"Parsed tenant from path: {tenant}")
        else:
            self.logger.info(f"Using explicitly provided tenant: {tenant}")
        
        self.logger.info(f"New connection: {session_id} for tenant '{tenant}'")
        self.logger.info(f"Connection path: {path}")
        self.logger.info(f"Final tenant used: {tenant}")
        
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
        self.logger.info(f"Server version: {websockets.__version__}")
        
        # Load tenant greeting configurations at startup
        self.logger.info("Loading tenant greeting configurations at startup...")
        await load_tenant_greeting_configs()
        self.logger.info("Tenant greeting configurations loaded successfully")
        
        # Create a WebSocket server
        async def handler(websocket, path=None):
            # Log the WebSocket object type and available attributes
            self.logger.info(f"WebSocket object type: {type(websocket)}")
            
            # If path is None, try to get it from the websocket object (depends on websockets version)
            if path is None:
                try:
                    path = websocket.path
                    self.logger.info(f"Got path from websocket.path: {path}")
                except AttributeError:
                    # If we can't get the path, assume it's the default path
                    path = '/media'
                    self.logger.info(f"No path attribute, using default: {path}")
            else:
                self.logger.info(f"Path provided directly to handler: {path}")
            
            # Log the raw path
            self.logger.info(f"Raw WebSocket path in handler: '{path}'")
            
            # Default tenant
            tenant = 'bakery'
            
            # Extract tenant from query parameters (Exotel passes custom parameters this way)
            if '?' in path:
                query_string = path.split('?', 1)[1]
                self.logger.info(f"Found query string: {query_string}")
                
                # Parse query parameters
                query_params = {}
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        query_params[key] = value
                
                self.logger.info(f"Query parameters: {query_params}")
                
                # Check for tenant parameter
                if 'tenant' in query_params:
                    tenant_param = query_params['tenant']
                    if tenant_param in ['saloon', 'bakery']:
                        tenant = tenant_param
                        self.logger.info(f"Found tenant in query parameters: {tenant}")
            
            # Fallback: Try to find tenant in path segments
            if tenant == 'bakery' and path:
                # Split path into segments
                path_segments = path.split('/')
                for segment in path_segments:
                    if segment in ['saloon', 'bakery']:
                        tenant = segment
                        self.logger.info(f"Found tenant in path segments: {tenant}")
                        break
            
            self.logger.info(f"Final tenant determination: {tenant}")
            
            # Handle the connection with the path and explicit tenant
            await self.handle_connection(websocket, path, tenant)
        
        # Start the server with robust configuration for voice calls
        server = await websockets.serve(
            handler,
            self.host,
            self.port,
            ping_interval=30,      # Send ping every 30 seconds (increased from default 20s)
            ping_timeout=15,       # Wait 15 seconds for pong response
            close_timeout=10,      # Don't wait forever to close connections
            max_size=2**20,        # 1MB max message size (sufficient for audio chunks)
            max_queue=64           # Allow reasonable message queue for concurrent calls
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
